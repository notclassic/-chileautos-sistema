# -*- coding: utf-8 -*-
"""
reparar_estado.py — Reconstruye estado_avisos.csv tras la corrida amputada
==========================================================================

Qué pasó: la corrida "Solo base" de la tarde del 08-07 corrió con la IP
bloqueada por Datadome, el catálogo se cortó en ~5.600 de 44.000 avisos y el
estado quedó reducido a esos sobrevivientes. Este script lo reconstruye desde
las bases del día (que están intactas en capturas/) sin perder nada:

  1. Respalda el estado actual.
  2. Reconstruye desde 'Chileautos 2026-07-08 AM.xlsx' (44.426 avisos con URL
     y teléfonos heredados).
  3. Le superpone el estado actual (los ~5.600 vistos en la tarde, que tienen
     el dato más fresco).
  4. Reescribe el export PM amputado con la base completa, para que mañana la
     rotación no vea 38.000 "vendidos" falsos.

Correr UNA vez, con el panel/goteos detenidos:  python reparar_estado.py
"""

import csv
import os
import shutil
import sys
from datetime import datetime

import pandas as pd

ESTADO = "estado_avisos.csv"
AM = os.path.join("capturas", "Chileautos 2026-07-08 AM.xlsx")
PM = os.path.join("capturas", "Chileautos 2026-07-08 PM.xlsx")

CAMPOS_ESTADO = [
    "id", "url", "marca", "modelo", "version", "año", "entidad",
    "traccion", "condicion", "kilometraje", "transmision", "combustible", "moneda",
    "precio", "precio_previo", "primera_vez", "ultima_vez", "veces_visto",
    "activo", "telefono", "whatsapp",
]

if not os.path.exists(AM):
    sys.exit(f"No encuentro {AM} — revisá el nombre exacto en capturas/.")

# 1. Respaldo
if os.path.exists(ESTADO):
    marca_t = datetime.now().strftime("%Y-%m-%d_%H-%M")
    resp = f"estado_avisos_backup_{marca_t}.csv"
    shutil.copy2(ESTADO, resp)
    print(f"Respaldo del estado actual: {resp}")

# 2. Estado actual (los ~5.600 con dato fresco de la tarde)
actual = {}
if os.path.exists(ESTADO):
    with open(ESTADO, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            i = str(row.get("id", "")).strip().upper()
            if i:
                actual[i] = row
print(f"Estado actual (amputado): {len(actual)} avisos")

# 3. Reconstrucción desde la base AM completa
df = pd.read_excel(AM)
print(f"Base AM: {len(df)} avisos")
estado = {}
for _, r in df.iterrows():
    i = str(r.get("id", "")).strip().upper()
    url = str(r.get("Enlace Web", "") or "").strip()
    if not i or not url.startswith("http"):
        continue
    fila = {c: "" for c in CAMPOS_ESTADO}
    fila.update({
        "id": i, "url": url,
        "marca": r.get("marca", ""), "modelo": r.get("modelo", ""),
        "version": r.get("version", ""), "año": r.get("año", ""),
        "entidad": r.get("entidad", ""), "traccion": r.get("traccion", ""),
        "condicion": r.get("condicion", ""), "kilometraje": r.get("kilometraje", ""),
        "transmision": r.get("transmision", ""), "combustible": r.get("combustible", ""),
        "moneda": r.get("moneda", ""), "precio": r.get("precio", ""),
        "precio_previo": "",
        "primera_vez": "2026-07-07",   # sembrados; los realmente nuevos se corrigen abajo
        "ultima_vez": "2026-07-08",
        "veces_visto": 2, "activo": 1,
        "telefono": ("" if pd.isna(r.get("telefono")) else r.get("telefono", "")),
        "whatsapp": ("" if pd.isna(r.get("whatsapp")) else r.get("whatsapp", "")),
    })
    estado[i] = fila

# 4. Superponer el estado actual (dato más fresco de la tarde) y conservar
#    primera_vez reales donde existían
for i, row in actual.items():
    if i in estado:
        for campo in CAMPOS_ESTADO:
            v = row.get(campo, "")
            if v not in ("", None):
                estado[i][campo] = v
    else:
        estado[i] = {c: row.get(c, "") for c in CAMPOS_ESTADO}

activos = sum(1 for f in estado.values() if str(f.get("activo", 1)) != "0")
con_url = sum(1 for f in estado.values() if str(f.get("url", "")).startswith("http"))
print(f"Estado reconstruido: {len(estado)} avisos | activos: {activos} | con URL: {con_url}")

# 5. Escritura atómica
tmp = ESTADO + ".tmp"
with open(tmp, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=CAMPOS_ESTADO, extrasaction="ignore")
    w.writeheader()
    for fila in estado.values():
        w.writerow(fila)
os.replace(tmp, ESTADO)
print(f"OK: {ESTADO} reescrito.")

# 6. Reemplazar el export PM amputado por la base completa
if os.path.exists(PM):
    shutil.move(PM, PM.replace(".xlsx", " (parcial, no usar).xlsx.bak"))
filas = [f for f in estado.values() if str(f.get("activo", 1)) != "0"]
out = pd.DataFrame(filas)
out = out.rename(columns={"url": "Enlace Web"})
cols = ["fecha"] if "fecha" in out.columns else []
out.insert(0, "fecha", "08-07-2026 20:00")
out.to_excel(PM, index=False)
print(f"OK: {PM} reescrito con {len(filas)} avisos activos.")
print("\nListo. Verificá con: python chequeo_estado.py")
