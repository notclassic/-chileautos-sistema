# -*- coding: utf-8 -*-
"""
clasificar_ia.py — Lectura inteligente de las descripciones (LLM vía Groq)
==========================================================================

Complementa a las palabras clave: un modelo de lenguaje LEE cada comentario
del vendedor y devuelve etiquetas, urgencia (0-10) y un resumen de una línea.
Entiende frases sin palabra exacta ("dueño se muda a Australia" = venta
urgente) que las listas de palabras no pueden captar.

- Procesa SOLO los comentarios nuevos (cache en comentarios_ia.json).
- En tandas de 8 por llamada para cuidar la cuota gratis de Groq.
- Sin API key o sin internet: avisa y termina en paz (la cadena sigue;
  las palabras clave quedan de respaldo).

Configurar UNA vez: crear el archivo  groq_key.txt  en esta carpeta con la
API key adentro (la misma que usa el bot de Kingdom), o definir la variable
de entorno GROQ_API_KEY.

Correr:  python clasificar_ia.py            (procesa lo nuevo)
         python clasificar_ia.py --limite 50 (tanda de prueba)
"""

import argparse
import json
import os
import sys
import time

import requests

ENTRADA = "comentarios.json"
SALIDA = "comentarios_ia.json"
MODELO = "llama-3.1-8b-instant"
URL = "https://api.groq.com/openai/v1/chat/completions"
TANDA = 8          # comentarios por llamada
PAUSA = 2.0        # segundos entre llamadas (cuota gratis)

ETIQUETAS_VALIDAS = [
    "venta_urgente", "precio_conversable", "daniado", "problema_legal",
    "km_dudoso", "unico_dueno", "pocos_duenos", "mantencion_al_dia",
    "impecable", "poco_uso", "listo_transferir", "facilidades",
    "origen_especial", "precio_condicionado", "precio_mas_iva",
    "modificado", "trato_directo",
]

INSTRUCCION = (
    "Eres un analista del mercado chileno de autos usados. Recibes comentarios "
    "escritos por vendedores. Para CADA comentario devuelve un objeto JSON con: "
    "id (el mismo recibido), etiquetas (lista, SOLO de estas permitidas: "
    + ", ".join(ETIQUETAS_VALIDAS) + "; lista vacía si ninguna aplica), "
    "urgencia (entero 0-10: 0=sin apuro, 10=remate desesperado), "
    "resumen (UNA frase corta en español con lo comercialmente relevante). "
    "Interpreta el sentido aunque no estén las palabras exactas: 'me voy del "
    "país' es venta_urgente; 'detalle en parachoque' es daniado; 'se puede "
    "conversar' es precio_conversable. Respeta las negaciones: 'nunca chocado' "
    "NO es daniado; 'precio NO conversable', 'precio firme', 'no negociable' o "
    "'precio fijo' NO es precio_conversable (es lo contrario). "
    " IMPORTANTE: 'precio publicado válido solo con financiamiento' "
    "o 'bono de financiamiento' es precio_condicionado (el precio contado real es "
    "mayor); 'más IVA' es precio_mas_iva; 'DPF eliminado' o 'adblue desconectado' "
    "es modificado. Responde SOLO un array JSON válido, sin texto adicional, "
    "sin markdown."
)


def log(msg):
    print(f"[ia] {msg}", flush=True)


def api_key():
    k = os.environ.get("GROQ_API_KEY", "").strip()
    if not k and os.path.exists("groq_key.txt"):
        k = open("groq_key.txt", encoding="utf-8").read().strip()
    return k


def cargar(ruta):
    if os.path.exists(ruta):
        try:
            with open(ruta, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def guardar(d):
    tmp = SALIDA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SALIDA)


def llamar_groq(key, lote):
    """lote = [(id, texto), ...] -> lista de dicts o None si falló."""
    contenido = json.dumps(
        [{"id": i, "comentario": t[:1200]} for i, t in lote], ensure_ascii=False)
    try:
        r = requests.post(URL, timeout=45, headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }, json={
            "model": MODELO,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": INSTRUCCION},
                {"role": "user", "content": contenido},
            ],
        })
    except Exception as e:
        log(f"error de conexión: {e}")
        return None
    if r.status_code == 429:
        log("cuota de Groq alcanzada por ahora; espero 60s...")
        time.sleep(60)
        return llamar_groq(key, lote)
    if r.status_code != 200:
        log(f"HTTP {r.status_code}: {r.text[:200]}")
        return None
    try:
        texto = r.json()["choices"][0]["message"]["content"].strip()
        if texto.startswith("```"):
            texto = texto.strip("`")
            texto = texto[texto.find("["):]
        datos = json.loads(texto[texto.find("["):texto.rfind("]") + 1])
        return datos if isinstance(datos, list) else None
    except Exception as e:
        log(f"respuesta no parseable ({e}); salto esta tanda.")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=0,
                    help="máximo de comentarios en esta pasada (0 = todos)")
    args = ap.parse_args()

    key = api_key()
    if not key:
        log("Sin API key de Groq (crear groq_key.txt). Salto la lectura IA; "
            "las palabras clave siguen funcionando solas.")
        return

    memoria = cargar(ENTRADA)
    hechos = cargar(SALIDA)
    pendientes = [(i, (d or {}).get("comentario", ""))
                  for i, d in memoria.items()
                  if i not in hechos and (d or {}).get("comentario", "").strip()]
    if args.limite > 0:
        pendientes = pendientes[:args.limite]
    if not pendientes:
        log("Nada nuevo que leer.")
        return
    log(f"Comentarios nuevos a leer con IA: {len(pendientes)} "
        f"(~{len(pendientes)//TANDA + 1} llamadas)")

    ok = fallidos = 0
    for n in range(0, len(pendientes), TANDA):
        lote = pendientes[n:n + TANDA]
        res = llamar_groq(key, lote)
        if res:
            ids_lote = {i for i, _ in lote}
            for obj in res:
                i = str(obj.get("id", "")).strip()
                if i not in ids_lote:
                    continue
                etiquetas = [e for e in (obj.get("etiquetas") or [])
                             if e in ETIQUETAS_VALIDAS]
                try:
                    urg = max(0, min(10, int(obj.get("urgencia", 0))))
                except (TypeError, ValueError):
                    urg = 0
                hechos[i] = {
                    "etiquetas_ia": etiquetas,
                    "urgencia": urg,
                    "resumen": str(obj.get("resumen", ""))[:200],
                }
                ok += 1
            guardar(hechos)
        else:
            fallidos += len(lote)
        if n + TANDA < len(pendientes):
            time.sleep(PAUSA)
        if (n // TANDA) % 10 == 9:
            log(f"  {ok} leídos...")

    log(f"Listo. Leídos con IA: {ok} | fallidos (reintentan la próxima): {fallidos} "
        f"| total acumulado: {len(hechos)}")


if __name__ == "__main__":
    main()
