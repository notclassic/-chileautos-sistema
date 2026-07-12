# -*- coding: utf-8 -*-
"""
sembrar_estado.py — Crea estado_avisos.csv desde la última base completa
========================================================================

Se corre UNA sola vez, después de una descarga completa (DESCARGAR_BASE.bat).

Qué hace:
  1. Busca el Excel más reciente "Chileautos AAAA-MM-DD.xlsx" en capturas/.
  2. Convierte cada aviso en una fila del estado acumulado, HEREDANDO el
     teléfono y whatsapp ya descargados.
  3. Escribe estado_avisos.csv.

Con eso, la primera corrida de actualizar_incremental.py NO trata a los
44.000 avisos como "nuevos": solo baja detalles de los que aparezcan
después de esta base.

Si estado_avisos.csv ya existe, pide confirmación antes de pisarlo.

Uso:  python sembrar_estado.py
"""

import csv
import glob
import os
import re
import sys

import pandas as pd

ESTADO = "estado_avisos.csv"
CARPETA = "capturas"

# Debe coincidir con CAMPOS_ESTADO de actualizar_incremental.py
CAMPOS_ESTADO = [
    "id", "url", "marca", "modelo", "version", "año", "entidad",
    "traccion", "condicion", "kilometraje", "transmision", "combustible", "moneda",
    "precio", "precio_previo", "primera_vez", "ultima_vez", "veces_visto",
    "activo", "telefono", "whatsapp",
]


def id_de_url(u):
    """Misma extracción de id que usa actualizar_incremental.py."""
    m = re.search(r"/((?:CP|CL|GI)-AD-\d+)", str(u), re.IGNORECASE)
    return m.group(1).upper() if m else ""


def main():
    # 1. Elegir la base más reciente
    candidatos = sorted(glob.glob(os.path.join(CARPETA, "Chileautos *.xlsx")))
    if not candidatos:
        print(f"No encontré ningún 'Chileautos AAAA-MM-DD.xlsx' en {CARPETA}/. Aborto.")
        sys.exit(1)
    ruta = max(candidatos, key=os.path.getmtime)  # la más reciente de verdad
    m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(ruta))
    fecha_base = m.group(1) if m else ""
    print(f"Base elegida: {ruta} (fecha {fecha_base or 'desconocida'})")

    # 2. No pisar un estado existente sin preguntar
    if os.path.exists(ESTADO):
        r = input(f"{ESTADO} ya existe y se va a REEMPLAZAR. ¿Seguro? (escribí SI): ")
        if r.strip().upper() != "SI":
            print("Cancelado. No se tocó nada.")
            sys.exit(0)

    df = pd.read_excel(ruta)
    df.columns = [str(c).strip() for c in df.columns]
    col_url = "Enlace Web" if "Enlace Web" in df.columns else ("url" if "url" in df.columns else None)

    # Las celdas de "Enlace Web" muestran "Abrir Publicación" y esconden la URL
    # en el hipervínculo. Las URLs reales se leen del XML interno del xlsx
    # (misma técnica que enriquecer_comentarios.py) y se indexan por id.
    url_por_id = {}
    try:
        import zipfile
        with zipfile.ZipFile(ruta) as z:
            rels = z.read("xl/worksheets/_rels/sheet1.xml.rels").decode("utf-8", "ignore")
        for u in re.findall(r'Target="([^"]+chileautos\.cl[^"]+)"', rels):
            i = id_de_url(u)
            if i:
                url_por_id[i] = u
    except Exception as e:
        print(f"Aviso: no pude leer hipervínculos del xlsx ({e}). Sigo con las celdas.")
    print(f"Hipervínculos con id reconocible dentro del xlsx: {len(url_por_id)}")

    ID_PAT = re.compile(r"(?:CP|CL|GI)-AD-\d+", re.IGNORECASE)

    def celda(fila, col):
        v = fila.get(col, "")
        return "" if pd.isna(v) else v

    estado = {}
    sin_id = 0
    for _, fila in df.iterrows():
        # id: primero la columna 'id' del Excel; si no, la celda de URL
        crudo = str(celda(fila, "id")).strip()
        m = ID_PAT.search(crudo)
        i = m.group(0).upper() if m else id_de_url(celda(fila, col_url) if col_url else "")
        if not i:
            sin_id += 1
            continue
        url = url_por_id.get(i, "")
        if not url:
            texto_celda = str(celda(fila, col_url)) if col_url else ""
            if "chileautos.cl" in texto_celda:
                url = texto_celda
        if i in estado:
            continue  # duplicado dentro de la misma base
        tel = str(celda(fila, "telefono")).strip()
        wsp = str(celda(fila, "whatsapp")).strip()
        estado[i] = {
            "id": i, "url": url,
            "marca": celda(fila, "marca"), "modelo": celda(fila, "modelo"),
            "version": celda(fila, "version"), "año": celda(fila, "año"),
            "entidad": celda(fila, "entidad"),
            "traccion": celda(fila, "traccion"), "condicion": celda(fila, "condicion"),
            "kilometraje": celda(fila, "kilometraje"),
            "transmision": celda(fila, "transmision"),
            "combustible": celda(fila, "combustible"), "moneda": celda(fila, "moneda"),
            "precio": celda(fila, "precio"), "precio_previo": "",
            "primera_vez": fecha_base, "ultima_vez": fecha_base,
            "veces_visto": 1, "activo": 1,
            "telefono": tel, "whatsapp": wsp,
        }

    with open(ESTADO, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_ESTADO)
        w.writeheader()
        for fila in estado.values():
            w.writerow({k: fila.get(k, "") for k in CAMPOS_ESTADO})

    con_tel = sum(1 for f in estado.values()
                  if f["telefono"] not in ("", "No disponible")
                  or f["whatsapp"] not in ("", "No disponible"))
    if not estado:
        print("\nPROBLEMA: no se reconoció ningún aviso. Muestras de la columna 'id':")
        for x in list(df.get("id", pd.Series(dtype=object)).head(3)):
            print("   id:", repr(x))
        print("Pasale estas líneas a Claude para diagnosticar.")
        sys.exit(1)

    print(f"\nListo: {ESTADO} creado con {len(estado)} avisos "
          f"({con_tel} con contacto heredado, {sin_id} filas descartadas sin id).")
    print("La próxima corrida de actualizar_incremental.py solo bajará "
          "detalles de avisos que no estén en esta base.")


if __name__ == "__main__":
    main()
