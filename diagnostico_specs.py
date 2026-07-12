# -*- coding: utf-8 -*-
"""
diagnostico_specs.py — Averigua por qué las specs no vienen.

Baja la página de 4 avisos (el Sail donde la ficha SEGURO existe, más los 3
que fallaron antes), guarda cada HTML en un archivo, y reporta:
  - código HTTP (200 o bloqueo 403)
  - si el HTML trae los marcadores de la ficha real
  - qué parseó el extractor corregido

Los HTML quedan guardados como specs_debug_1.html, specs_debug_2.html, etc.
Si algo sigue fallando, esos archivos son los que hay que revisar.

Correr:  python diagnostico_specs.py
"""

import asyncio
import sys
from curl_cffi.requests import AsyncSession

from especificaciones import parsear_especificaciones, headers_base

URLS = [
    # El Sail: Maria confirmó a ojo que la ficha completa existe en este aviso
    "https://www.chileautos.cl/vehiculos/detalles/2026-chevrolet-sail-1-5-nb-ltz-r-4x2-sdn-cvt-at-4p/CP-AD-8533095",
    # Los 3 que fallaron en la prueba anterior
    "https://www.chileautos.cl/vehiculos/detalles/2018-bmw-x1-bmw-x1-sdrive-20i-2-0/CP-AD-8532255",
    "https://www.chileautos.cl/vehiculos/detalles/toyota-land-cruiser-prado-tx-2013/GI-AD-913507",
    "https://www.chileautos.cl/vehiculos/detalles/2011-bmw-316-i/CP-AD-8530251",
]

MARCADORES = ["Cilindrada exacta", "Distancia entre ejes", "Torque", "Especificaciones"]


async def main():
    async with AsyncSession() as session:
        for i, url in enumerate(URLS, 1):
            print(f"\n===== Aviso {i}/{len(URLS)} =====")
            print(url)
            try:
                resp = await session.get(url, headers=headers_base,
                                         impersonate="chrome99_android", timeout=10)
            except Exception as e:
                print(f"   ERROR de conexión: {e}")
                continue

            print(f"   HTTP: {resp.status_code} | tamaño: {len(resp.text):,} caracteres")

            nombre = f"specs_debug_{i}.html"
            with open(nombre, "w", encoding="utf-8") as f:
                f.write(resp.text)
            print(f"   HTML guardado en {nombre}")

            if resp.status_code != 200:
                print("   -> Bloqueado. No hay nada que parsear.")
                continue

            for m in MARCADORES:
                print(f"   '{m}' en el HTML: {'SÍ' if m in resp.text else 'NO'}")

            limpios, crudos = parsear_especificaciones(resp.text)
            print(f"   Pares hallados: {len(crudos)} | Ficha válida: {'SÍ' if limpios else 'NO'}")
            if limpios:
                print(f"   version_oficial: {limpios.get('version_oficial')}")
                print(f"   cilindrada_cc: {limpios.get('cilindrada_cc')} | "
                      f"power: {limpios.get('power_hp')} | torque: {limpios.get('torque_nm')}")

            # pausa corta entre avisos para no provocar bloqueos
            await asyncio.sleep(3)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
