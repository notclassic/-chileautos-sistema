# -*- coding: utf-8 -*-
"""
bajar_especificaciones.py — Goteo de especificaciones (ficha técnica)
=====================================================================

Baja la ficha de Especificaciones de los avisos, UNO POR UNO y despacio,
con la misma filosofía que el goteo de descripciones: pausas aleatorias,
descanso largo cada tanto, y rendición ante bloqueos en cadena (para no
pelearse con Datadome).

Prioridad: 1) oportunidades del radar (datos.json), 2) avisos más nuevos.

Guarda en especificaciones.csv (id, url + columnas de la ficha). Guarda a
medida que avanza: se puede cortar con Ctrl+C sin perder nada.

Al final imprime un DIAGNÓSTICO: con una tanda chica (--limite 20) alcanza
para saber si las specs están en el HTML, si la IP está bloqueada, o si
hay que cazar una API aparte.

Uso:
    python bajar_especificaciones.py --limite 20      (prueba diagnóstica)
    python bajar_especificaciones.py --limite 300     (tanda normal)
    python bajar_especificaciones.py --solo-nuevos    (solo los de hoy + radar)
"""

import argparse
import csv
import json
import os
import random
import sys
import time
from datetime import date

try:
    from curl_cffi.requests import Session
except ImportError:
    sys.exit("Falta curl_cffi. Instalar con: pip install curl_cffi")

from especificaciones import parsear_especificaciones, headers_base, COLUMNAS_SPECS

ESTADO = "estado_avisos.csv"
SALIDA = "especificaciones.csv"          # resumen: columnas clave para el motor
SALIDA_FULL = "especificaciones_full.json"  # ficha COMPLETA de cada aviso, tal cual viene
DATOS = "datos.json"

PAUSA = (4, 11)            # segundos entre avisos
PAUSA_LARGA_CADA = 40      # cada tantos avisos...
PAUSA_LARGA = (45, 90)     # ...pausa larga
ESPERA_BLOQUEO = 600       # 10 min tras un 403
MAX_BLOQUEOS_SEGUIDOS = 3  # a la tercera en cadena, se rinde por hoy


def log(msg):
    print(f"[specs] {msg}", flush=True)


def cargar_full():
    if os.path.exists(SALIDA_FULL):
        try:
            with open(SALIDA_FULL, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def guardar_full(d):
    tmp = SALIDA_FULL + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SALIDA_FULL)


def ids_ya_bajados():
    hechos = set()
    if os.path.exists(SALIDA):
        with open(SALIDA, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                i = str(row.get("id", "")).strip().upper()
                if i:
                    hechos.add(i)
    return hechos


def armar_pendientes(solo_nuevos):
    if not os.path.exists(ESTADO):
        sys.exit(f"No existe {ESTADO}. Corré primero sembrar_estado.py.")
    hoy = date.today().isoformat()

    radar = set()
    try:
        if os.path.exists(DATOS):
            with open(DATOS, encoding="utf-8") as f:
                for o in (json.load(f).get("oportunidades") or []):
                    i = str(o.get("id") or "").strip().upper()
                    if i:
                        radar.add(i)
    except Exception:
        pass

    hechos = ids_ya_bajados()
    filas = []
    with open(ESTADO, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            i = str(row.get("id", "")).strip().upper()
            u = (row.get("url") or "").strip()
            if not i or not u or i in hechos:
                continue
            if str(row.get("activo", "1")) == "0":
                continue
            pv = (row.get("primera_vez") or "").strip()
            if solo_nuevos and pv != hoy and i not in radar:
                continue
            es_part = (row.get("entidad") or "").strip().lower() == "particular"
            filas.append((i in radar, es_part, pv, i, u))

    # radar primero; luego PARTICULARES antes que automotoras; dentro de
    # cada grupo, los más nuevos primero
    filas.sort(reverse=True)
    return [(i, u) for _, _, _, i, u in filas], len(radar & {f[3] for f in filas})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=300,
                    help="máximo de avisos por tanda (0 = sin límite, toma todos)")
    ap.add_argument("--solo-nuevos", action="store_true",
                    help="solo avisos de hoy + oportunidades del radar sin specs")
    args = ap.parse_args()

    pendientes, en_radar = armar_pendientes(args.solo_nuevos)
    if not pendientes:
        log("No hay avisos pendientes de specs con este filtro. Nada que hacer.")
        return
    tanda = pendientes if args.limite <= 0 else pendientes[:args.limite]
    log(f"Pendientes totales: {len(pendientes)} (de ellos, {en_radar} en el radar). "
        f"Esta tanda: {len(tanda)}.")

    # preparar CSV (mismo formato que usa actualizar_incremental)
    existe = os.path.exists(SALIDA)
    f_out = open(SALIDA, "a", encoding="utf-8", newline="")
    w = csv.writer(f_out)
    if not existe:
        w.writerow(["id", "url"] + COLUMNAS_SPECS)

    full = cargar_full()
    ok = sin_ficha = errores = 0
    codigos = {}
    bloqueos_seguidos = 0
    rendido = False
    n = 0
    idx = 0

    try:
        with Session() as s:
            while idx < len(tanda):
                i, url = tanda[idx]
                try:
                    resp = s.get(url, headers=headers_base,
                                 impersonate="chrome99_android", timeout=12)
                    code = resp.status_code
                except Exception as e:
                    log(f"{i}: error de conexión ({e}). Sigo con el próximo.")
                    errores += 1
                    idx += 1
                    time.sleep(random.uniform(*PAUSA))
                    continue

                codigos[code] = codigos.get(code, 0) + 1

                if code in (403, 429):
                    bloqueos_seguidos += 1
                    if bloqueos_seguidos >= MAX_BLOQUEOS_SEGUIDOS:
                        log(f"{i}: bloqueo {code}. Tercer bloqueo en cadena: me rindo "
                            f"por hoy para no reforzar el bloqueo.")
                        rendido = True
                        break
                    log(f"{i}: bloqueo {code}. Espero {ESPERA_BLOQUEO//60} min y reintento "
                        f"(bloqueo {bloqueos_seguidos}/{MAX_BLOQUEOS_SEGUIDOS})...")
                    time.sleep(ESPERA_BLOQUEO)
                    continue  # mismo aviso, sin avanzar

                bloqueos_seguidos = 0

                if code == 200:
                    limpios, crudos = parsear_especificaciones(resp.text)
                    if crudos:
                        fila = dict(crudos)
                        fila.update(limpios)
                        w.writerow([i, url] + [fila.get(c, "") for c in COLUMNAS_SPECS])
                        f_out.flush()
                        # ficha completa, con TODOS los campos que traiga este aviso
                        full[i] = {"url": url, "campos": crudos, "clave": limpios}
                        guardar_full(full)
                        ok += 1
                        n_campos = len(crudos)
                        log(f"{i}: ficha OK, {n_campos} campos "
                            f"({limpios.get('version_oficial', 'sin versión')})")
                    else:
                        sin_ficha += 1
                        log(f"{i}: página OK pero SIN ficha en el HTML.")
                else:
                    errores += 1
                    log(f"{i}: HTTP {code}.")

                idx += 1
                n += 1
                if n % PAUSA_LARGA_CADA == 0:
                    t = random.uniform(*PAUSA_LARGA)
                    log(f"Pausa larga de {t:.0f}s ({n} visitados)...")
                    time.sleep(t)
                else:
                    time.sleep(random.uniform(*PAUSA))
    except KeyboardInterrupt:
        log("Cortado a mano. Lo bajado hasta acá quedó guardado.")
    finally:
        f_out.close()

    # ------------------- DIAGNÓSTICO -------------------
    print("\n========== RESUMEN ==========")
    print(f"Visitados: {idx} | Fichas válidas: {ok} | Sin ficha: {sin_ficha} | "
          f"Errores: {errores} | Códigos HTTP: {codigos}")
    n200 = codigos.get(200, 0)
    n403 = codigos.get(403, 0) + codigos.get(429, 0)
    print("\nLectura del resultado:")
    if rendido or (n403 and n200 == 0):
        print("  -> BLOQUEO: Datadome está cortando esta IP. No es un problema del")
        print("     código. Dejar descansar unas horas y probar de nuevo con --limite 20.")
    elif n200 and ok == 0 and sin_ficha >= max(3, n200 // 2):
        print("  -> LAS SPECS NO ESTÁN EN EL HTML: la página carga pero la ficha no")
        print("     viene adentro. Hay que cazar la API con el navegador:")
        print("     F12 > Network > Fetch/XHR > abrir la pestaña Especificaciones de")
        print("     un aviso > copiar la URL que aparece > pasársela a Claude.")
    elif ok:
        print(f"  -> FUNCIONA: {ok} fichas bajadas. Se puede activar en la rutina diaria.")
        print("     Los primeros specs_debug ya no hacen falta.")
    else:
        print("  -> Resultado mixto: pegale este resumen completo a Claude.")


if __name__ == "__main__":
    main()
