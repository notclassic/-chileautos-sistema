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
    except KeyError:
        pass  # base del sistema nuevo: sin hipervinculos (las URLs viven en el estado)
    except Exception as e:
        log(f"  aviso leyendo {os.path.basename(path)}: {e}")
    return out


ESTADO_INCREMENTAL = "estado_avisos.csv"


def reunir_pendientes(memoria, solo_nuevos=False):
    """
    Junta id -> url de dos fuentes y devuelve los pendientes ORDENADOS con los
    avisos mas nuevos primero (por fecha de primera aparicion):

      1. estado_avisos.csv (el sistema incremental): trae la fecha exacta en
         que cada aviso se vio por primera vez. Fuente principal.
      2. Los hipervinculos de las capturas .xlsx (metodo historico): respaldo
         para avisos anteriores al estado o si el estado no existe.

    solo_nuevos=True: se queda UNICAMENTE con los avisos cuya primera
    aparicion es HOY (los detectados por la corrida incremental de hoy).
    """
    from datetime import date
    hoy_iso = date.today().isoformat()

    id_url = {}
    primera = {}   # id -> fecha ISO de primera aparicion ("" = desconocida/vieja)
    particular = set()   # ids cuyo vendedor es Particular (prioridad de descarga)

    # Fuente 1: estado del incremental (manda: define QUE se descarga)
    vivos = None   # None = no hay estado; set = solo estos son descargables
    if os.path.exists(ESTADO_INCREMENTAL):
        vivos = set()
        import csv as _csv
        with open(ESTADO_INCREMENTAL, encoding="utf-8", newline="") as f:
            for row in _csv.DictReader(f):
                u = (row.get("url") or "").strip()
                if not u:
                    continue
                vid = u.rstrip('/').split('/')[-1].lower()
                id_url[vid] = u
                primera[vid] = (row.get("primera_vez") or "").strip()
                if (row.get("entidad") or "").strip().lower() == "particular":
                    particular.add(vid)
                if str(row.get("activo", "1")) != "0":
                    vivos.add(vid)

    # Fuente 2: capturas (respaldo / historico)
    archivos = sorted(glob.glob(os.path.join(CARPETA_CAPTURAS, "*.xlsx")))
    if not archivos and not id_url:
        sys.exit(f"No hay capturas en '{CARPETA_CAPTURAS}' ni {ESTADO_INCREMENTAL}.")
    for path in archivos:
        for i, u in leer_urls_de_captura(path).items():
            id_url.setdefault(i, u)
            primera.setdefault(i, "")

    # Prioridad maxima: los avisos que HOY figuran en el radar de oportunidades
    # (datos.json). Su descripcion es la que se necesita ANTES de llamar.
    radar = set()
    try:
        if os.path.exists("datos.json"):
            import json as _json
            with open("datos.json", encoding="utf-8") as f:
                for o in (_json.load(f).get("oportunidades") or []):
                    i = str(o.get("id") or "").lower()
                    if i:
                        radar.add(i)
    except Exception:
        pass

    pend_ids = [i for i in id_url if i not in memoria]
    if vivos is not None:
        # sin gastar pedidos en avisos muertos o dados de baja hace meses
        pend_ids = [i for i in pend_ids if i in vivos]
    if solo_nuevos:
        pend_ids = [i for i in pend_ids if primera.get(i) == hoy_iso or i in radar]
    # Orden: 1) oportunidades del radar, 2) PARTICULARES antes que automotoras
    # (ahi esta el negocio), 3) mas nuevos primero (ISO ordena bien como
    # texto; "" = viejo, queda al final)
    pend_ids.sort(key=lambda i: (i in radar, i in particular,
                                 primera.get(i, "")), reverse=True)
    pendientes = {i: id_url[i] for i in pend_ids}
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
    ap.add_argument('--continuo', action='store_true',
                    help='modo goteo: nunca termina, vuelve a buscar nuevos cada tanto')
    ap.add_argument('--solo-nuevos', action='store_true',
                    help='procesar SOLO los avisos detectados como nuevos HOY por el incremental')
    args = ap.parse_args()

    pmin, pmax = (PAUSA_MIN_RAPIDO, PAUSA_MAX_RAPIDO) if args.rapido else (PAUSA_MIN, PAUSA_MAX)

    if args.continuo:
        modo_continuo(pmin, pmax)
        return

    _una_pasada(pmin, pmax, args.limite, solo_nuevos=args.solo_nuevos)


def modo_continuo(pmin, pmax):
    """
    Goteo permanente: procesa los pendientes, y cuando no quedan, espera un
    rato (con algo de azar) y vuelve a buscar publicaciones nuevas. No termina
    hasta que lo cortes con Ctrl+C. Pensado para dejarlo corriendo todo el dia.
    """
    ESPERA_SIN_NUEVOS_MIN = 600    # 10 min si no hay nada nuevo
    ESPERA_SIN_NUEVOS_MAX = 1200   # 20 min
    log("MODO CONTINUO (goteo). Dejalo corriendo. Cortar con Ctrl+C.")
    log("Procesa lo nuevo, guarda, y cada tanto vuelve a mirar.\n")
    while not _parar:
        procesados = _una_pasada(pmin, pmax, 0, silencioso_si_vacio=True)
        if _parar:
            break
        if procesados == 0:
            espera = random.uniform(ESPERA_SIN_NUEVOS_MIN, ESPERA_SIN_NUEVOS_MAX)
            log(f"Sin publicaciones nuevas. Vuelvo a mirar en {espera/60:.0f} min.")
            # dormir en tramos para poder cortar con Ctrl+C
            t = 0
            while t < espera and not _parar:
                time.sleep(2)
                t += 2
    log("Modo continuo detenido.")


def _una_pasada(pmin, pmax, limite, silencioso_si_vacio=False, solo_nuevos=False):
    """Procesa los pendientes una vez. Devuelve cuantos proceso."""
    memoria = cargar_memoria()
    id_url, pendientes = reunir_pendientes(memoria, solo_nuevos=solo_nuevos)
    total_pend = len(pendientes)

    if total_pend == 0:
        if not silencioso_si_vacio:
            if solo_nuevos:
                log("No hay avisos NUEVOS de hoy sin descripcion. Nada que hacer.")
            else:
                log(f"Avisos en memoria: {len(memoria)} | total conocidos: {len(id_url)}")
                log("Nada que hacer. Todo enriquecido.")
        return 0

    log(f"Pendientes: {total_pend} | en memoria: {len(memoria)}")
    objetivo = limite if limite > 0 else total_pend
    log(f"Proceso hasta {min(objetivo, total_pend)}. "
        f"Ritmo {pmin}-{pmax}s entre avisos. Ctrl+C para cortar.\n")

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
                        log("  Demasiados bloqueos seguidos. Corto para no insistir.")
                        break
                    time.sleep(ESPERA_BLOQUEO)
                    continue
                else:
                    log(f"  HTTP {resp.status_code} en {idv}, lo salto.")
            except Exception as e:
                log(f"  Error en {idv}: {e}")

            procesados += 1

            if procesados % 25 == 0:
                guardar_memoria(memoria)
                elapsed = time.time() - inicio
                vel = procesados / elapsed if elapsed else 0
                rest = min(objetivo, total_pend) - procesados
                eta = time.strftime('%H:%M:%S', time.gmtime(rest / vel)) if vel else '?'
                log(f"  {procesados} procesados | {con_texto} con comentario | ETA {eta}")

            if procesados % CADA_N_PAUSA_LARGA == 0:
                time.sleep(random.uniform(PAUSA_LARGA_MIN, PAUSA_LARGA_MAX))
            else:
                time.sleep(random.uniform(pmin, pmax))

    guardar_memoria(memoria)
    log(f"Pasada terminada. Procesados {procesados} | con comentario {con_texto} | "
        f"memoria total {len(memoria)}.")
    return procesados



if __name__ == '__main__':
    main()
