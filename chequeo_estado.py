# -*- coding: utf-8 -*-
"""
chequeo_estado.py — Radiografía rápida de estado_avisos.csv.
Correr:  python chequeo_estado.py
"""
import csv
import sys

try:
    with open("estado_avisos.csv", encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
except FileNotFoundError:
    sys.exit("No existe estado_avisos.csv en esta carpeta.")

total = len(filas)
con_url = sum(1 for r in filas if (r.get("url") or "").strip())
activos = sum(1 for r in filas if str(r.get("activo", "1")) != "0")
activos_con_url = sum(1 for r in filas
                      if str(r.get("activo", "1")) != "0"
                      and (r.get("url") or "").strip())

print(f"Filas totales:        {total:>7,}".replace(",", "."))
print(f"Con URL:              {con_url:>7,}".replace(",", "."))
print(f"Activos:              {activos:>7,}".replace(",", "."))
print(f"Activos CON url:      {activos_con_url:>7,}".replace(",", "."))
print()
sin_url = [r for r in filas if not (r.get("url") or "").strip()][:3]
if sin_url:
    print("Ejemplos de filas SIN url:")
    for r in sin_url:
        print("  ", {k: r.get(k, "") for k in ("id", "primera_vez", "ultima_vez", "activo")})
else:
    print("Todas las filas tienen url.")
