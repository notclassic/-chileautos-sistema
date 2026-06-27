#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ENRIQUECEDOR DE COMENTARIOS - pieza nocturna del sistema Chileautos
====================================================================

Que hace:
  - Lee las capturas (.xlsx) de la carpeta capturas/ para saber que avisos
    existen y cual es la URL de cada uno.
  - Mantiene una MEMORIA (comentarios.json) con los comentarios ya capturados.
  - Visita SOLO los avisos cuyo comentario todavia no tiene (publicaciones
    nuevas), uno por uno, LENTO y con pausas aleatorias, para no ser
    bloqueado por Datadome.
  - Guarda a medida que avanza: si se corta, la proxima vez retoma donde quedo.

Lo que NO hace:
  - No re-visita avisos que ya tienen comentario.
  - No va rapido. La prioridad es no ser bloqueado, no la velocidad.

Filosofia de diseno (acordada):
  - La DETECCION de oportunidades la hace el scraper rapido + el motor (API,
    minutos). Esta pieza solo AGREGA el comentario, que sirve para validar
    si una oportunidad es real o es chatarra ("chocado", "para desarme").
  - Por eso puede correr de madrugada, lento, sin estorbar la deteccion.

Uso:
    python enriquecer_comentarios.py                 # procesa lo que falte
    python enriquecer_comentarios.py --limite 500    # corta tras 500 avisos (tandas)
    python enriquecer_comentarios.py --rapido        # pausas mas cortas (mas riesgo)

Requiere: pandas, openpyxl, curl_cffi, beautifulsoup4
(las mismas librerias del scraper)
"""

import os, sys, json, glob, time, random, argparse, signal
import pandas as pd

# Reutiliza la extraccion ya validada con la pagina real del Jeep
from comentario_vendedor import extraer_comentario_de_html

try:
    from curl_cffi.requests import Session
except ImportError:
    sys.exit("Falta curl_cffi. Instalalo con: pip install curl_cffi")

# ---------------------------------------------------------------------------
# CONFIGURACION
# ---------------------------------------------------------------------------
CARPETA_CAPTURAS = "capturas"
MEMORIA = "comentarios.json"        # acumula {id: {comentario, fecha_captura, url}}

# Ritmo lento (segundos de pausa entre visitas). Aleatorio dentro del rango.
PAUSA_MIN, PAUSA_MAX = 4.0, 11.0     # modo normal (nocturno, seguro)
PAUSA_MIN_RAPIDO, PAUSA_MAX_RAPIDO = 1.5, 4.0   # modo --rapido (mas riesgo)

# Pausa larga ocasional, para parecer mas humano y bajar presion
CADA_N_PAUSA_LARGA = 40             # cada ~40 avisos
PAUSA_LARGA_MIN, PAUSA_LARGA_MAX = 30.0, 90.0

# Si Datadome bloquea (403/429), frenar fuerte
ESPERA_BLOQUEO = 600               # 10 min
MAX_BLOQUEOS_SEGUIDOS = 3          # tras 3 bloqueos seguidos, abortar la corrida

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "es,es-ES;q=0.9,en;q=0.8",
    "user-agent": "Mozilla/5.0 (Linux; Android 13; SM-G981B) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
    "referer": "https://www.chileautos.cl/vehiculos/autos-veh%C3%ADculo/",
}

_parar = False  # para corte limpio con Ctrl+C


def _manejar_ctrlc(sig, frame):
    global _parar
    print("\n[enriquecer] Corte pedido. Termino el aviso actual y guardo...")
    _parar = True


signal.signal(signal.SIGINT, _manejar_ctrlc)


def log(m):
    print(f"[enriquecer] {m}")


# ---------------------------------------------------------------------------
# Memoria de comentarios (persistencia + retomar)
# ---------------------------------------------------------------------------
def cargar_memoria():
    if os.path.exists(MEMORIA):
        with open(MEMORIA, encoding='utf-8') as f:
            return json.load(f)
    return {}


def guardar_memoria(mem):
    tmp = MEMORIA + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(mem, f, ensure_ascii=False)
    os.replace(tmp, MEMORIA)  # escritura atomica: no corrompe si se corta


# ---------------------------------------------------------------------------
# Reunir avisos pendientes (id -> url) desde las capturas
# ---------------------------------------------------------------------------
def leer_urls_de_captura(path):
    """
    Devuelve {id: url} leyendo los hipervinculos directo del XML del xlsx.
    Mucho mas rapido que openpyxl (medio segundo vs >1 min por captura).
    El id del vehiculo se toma del final de la propia URL (ej .../GI-AD-860871).
    """
    import zipfile, re
    out = {}
    try:
        with zipfile.ZipFile(path) as z:
            rels = z.read('xl/worksheets/_rels/sheet1.xml.rels').decode('utf-8', 'ignore')
        urls = re.findall(r'Target="([^"]+chileautos\.cl[^"]+)"', rels)
        for u in urls:
            vid = u.rstrip('/').split('/')[-1].lower()   # id al final de la URL (en minuscula, como en la base)
            if vid:
                out[vid] = u
    except Exception as e:
        log(f"  aviso leyendo {os.path.basename(path)}: {e}")
    return out


def reunir_pendientes(memoria):
    archivos = sorted(glob.glob(os.path.join(CARPETA_CAPTURAS, "*.xlsx")))
    if not archivos:
        sys.exit(f"No hay capturas en '{CARPETA_CAPTURAS}'.")
    # id -> url, priorizando la captura mas reciente
    id_url = {}
    for path in archivos:
        id_url.update(leer_urls_de_captura(path))
    # pendientes = los que no estan en memoria
    pendientes = {i: u for i, u in id_url.items() if i not in memoria}
    return id_url, pendientes


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limite', type=int, default=0,
                    help='maximo de avisos a procesar en esta corrida (0 = sin limite)')
    ap.add_argument('--rapido', action='store_true',
                    help='pausas mas cortas (mas riesgo de bloqueo)')
    args = ap.parse_args()

    pmin, pmax = (PAUSA_MIN_RAPIDO, PAUSA_MAX_RAPIDO) if args.rapido else (PAUSA_MIN, PAUSA_MAX)

    memoria = cargar_memoria()
    id_url, pendientes = reunir_pendientes(memoria)
    total_pend = len(pendientes)

    log(f"Avisos en memoria: {len(memoria)} | total en capturas: {len(id_url)}")
    log(f"Pendientes (publicaciones nuevas sin comentario): {total_pend}")
    if total_pend == 0:
        log("Nada que hacer. Todo enriquecido.")
        return

    objetivo = args.limite if args.limite > 0 else total_pend
    log(f"Voy a procesar hasta {min(objetivo, total_pend)} en esta corrida. "
        f"Ritmo: {'rapido' if args.rapido else 'lento'} ({pmin}-{pmax}s entre avisos).")
    log("Cortar con Ctrl+C en cualquier momento: guarda y se puede retomar.\n")

    procesados = 0
    con_texto = 0
    bloqueos_seguidos = 0
    inicio = time.time()

    with Session() as session:
        for idv, url in pendientes.items():
            if _parar or procesados >= objetivo:
                break
            try:
                resp = session.get(url, headers=HEADERS,
                                   impersonate="chrome99_android", timeout=8)
                if resp.status_code == 200:
                    comentario = extraer_comentario_de_html(resp.text)
                    memoria[idv] = {'comentario': comentario, 'url': url}
                    if comentario:
                        con_texto += 1
                    bloqueos_seguidos = 0
                elif resp.status_code in (403, 429):
                    bloqueos_seguidos += 1
                    log(f"  BLOQUEO {resp.status_code} (#{bloqueos_seguidos}). "
                        f"Espero {ESPERA_BLOQUEO//60} min...")
                    if bloqueos_seguidos >= MAX_BLOQUEOS_SEGUIDOS:
                        log("  Demasiados bloqueos seguidos. Corto la corrida para "
                            "no insistir. Proba mas tarde o mas lento.")
                        break
                    time.sleep(ESPERA_BLOQUEO)
                    continue
                else:
                    log(f"  HTTP {resp.status_code} en {idv}, lo salto.")
            except Exception as e:
                log(f"  Error en {idv}: {e}")

            procesados += 1

            # Guardar cada 25 para no perder avance si se corta
            if procesados % 25 == 0:
                guardar_memoria(memoria)
                elapsed = time.time() - inicio
                vel = procesados / elapsed if elapsed else 0
                rest = min(objetivo, total_pend) - procesados
                eta = time.strftime('%H:%M:%S', time.gmtime(rest / vel)) if vel else '?'
                log(f"  {procesados} procesados | {con_texto} con comentario | ETA {eta}")

            # Pausa aleatoria (defensa principal sin proxies)
            if procesados % CADA_N_PAUSA_LARGA == 0:
                time.sleep(random.uniform(PAUSA_LARGA_MIN, PAUSA_LARGA_MAX))
            else:
                time.sleep(random.uniform(pmin, pmax))

    guardar_memoria(memoria)
    log(f"\nCorrida terminada. Procesados {procesados} | con comentario {con_texto} | "
        f"memoria total {len(memoria)}.")
    if not _parar and procesados < total_pend:
        log(f"Quedan {total_pend - procesados} pendientes. Volve a correr para seguir.")


if __name__ == '__main__':
    main()
