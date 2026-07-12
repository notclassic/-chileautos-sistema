#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLASIFICADOR DE COMENTARIOS
===========================
Lee comentarios.json (el que genera enriquecer_comentarios.py), clasifica
cada comentario por palabras clave y guarda etiquetas en comentarios_clasificados.json.

Detecta ademas:
  - NEGACIONES: "no chocado", "sin detalles" -> no marca daniado.
  - PLANTILLAS de automotora: comentarios identicos repetidos en muchos avisos
    (no describen el auto, son marketing). Se marcan con la etiqueta "plantilla".

Uso:
    python clasificar_comentarios.py

Salida: comentarios_clasificados.json
        { id: { "comentario": "...", "etiquetas": [...], "url": "..." } }

No requiere internet. Solo lee archivos locales.
"""

import json, os, re, unicodedata, sys
from collections import Counter

try:
    from palabras_clave import CATEGORIAS, NEGADORES
except ImportError:
    sys.exit("Falta el archivo palabras_clave.py en la misma carpeta.")

ENTRADA = "comentarios.json"
SALIDA = "comentarios_clasificados.json"

# Si un mismo comentario (casi identico) aparece en mas de este nro de avisos,
# se considera plantilla de automotora.
UMBRAL_PLANTILLA = 3


def normalizar(texto: str) -> str:
    """minuscula + sin acentos, para que la busqueda no dependa de tildes."""
    texto = texto.lower()
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return texto


def viene_negada(texto_norm: str, palabra: str) -> bool:
    """Revisa si la palabra aparece negada (ej 'no chocado', 'sin detalle')."""
    for m in re.finditer(re.escape(palabra), texto_norm):
        ini = m.start()
        # mirar las ~3 palabras anteriores
        previo = texto_norm[max(0, ini - 25):ini]
        if any(neg in previo.split() or previo.strip().endswith(neg) for neg in NEGADORES):
            return True
    return False


def etiquetar(texto: str) -> list:
    """Devuelve la lista de etiquetas que aplican a un comentario."""
    t = normalizar(texto)
    etiquetas = []
    for categoria, palabras in CATEGORIAS.items():
        for palabra in palabras:
            p = normalizar(palabra)
            if p in t:
                # las banderas rojas respetan negacion ("no chocado", "sin deuda")
                if categoria in ("daniado", "problema_legal") and viene_negada(t, p):
                    continue
                etiquetas.append(categoria)
                break  # con una palabra de la categoria basta
    return etiquetas


def firma(texto: str) -> str:
    """Firma corta para detectar comentarios repetidos (plantillas)."""
    t = normalizar(texto)
    t = re.sub(r'[^a-z0-9 ]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:120]  # primeros 120 chars normalizados


def main():
    if not os.path.exists(ENTRADA):
        sys.exit(f"No existe {ENTRADA}. Corre primero enriquecer_comentarios.py")

    with open(ENTRADA, encoding='utf-8') as f:
        data = json.load(f)

    # 1) detectar plantillas: firmas que se repiten mucho
    firmas = Counter()
    for d in data.values():
        c = d.get('comentario', '')
        if c:
            firmas[firma(c)] += 1
    plantillas = {fz for fz, n in firmas.items() if n >= UMBRAL_PLANTILLA}

    # 1b) lectura IA (clasificar_ia.py), si existe: se FUSIONA con las
    # palabras clave. La IA entiende el sentido; las palabras son el respaldo.
    ia = {}
    if os.path.exists('comentarios_ia.json'):
        try:
            with open('comentarios_ia.json', encoding='utf-8') as f:
                ia = json.load(f)
            print(f"Lectura IA cargada: {len(ia)} comentarios")
        except Exception as e:
            print(f"  aviso: comentarios_ia.json ilegible ({e})")

    # 2) clasificar
    salida = {}
    conteo = Counter()
    for idv, d in data.items():
        c = d.get('comentario', '') or ''
        etiquetas = etiquetar(c) if c else []
        lectura = ia.get(idv) or {}
        etiquetas += [e for e in (lectura.get('etiquetas_ia') or [])]
        if c and firma(c) in plantillas:
            etiquetas.append('plantilla')
        if not c:
            etiquetas.append('sin_comentario')
        for e in set(etiquetas):
            conteo[e] += 1
        salida[idv] = {'comentario': c, 'etiquetas': sorted(set(etiquetas)),
                       'url': d.get('url', ''),
                       'urgencia': lectura.get('urgencia', 0),
                       'resumen_ia': lectura.get('resumen', '')}

    with open(SALIDA, 'w', encoding='utf-8') as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)

    # reporte
    print(f"Clasificados: {len(salida)} comentarios")
    print(f"Plantillas de automotora detectadas: {len([1 for v in salida.values() if 'plantilla' in v['etiquetas']])}")
    print("\nConteo por etiqueta:")
    for et, n in conteo.most_common():
        print(f"  {et}: {n}")
    print(f"\nGuardado en {SALIDA}")


if __name__ == '__main__':
    main()
