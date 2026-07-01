# -*- coding: utf-8 -*-
"""
probar_especificaciones.py — Prueba el extractor de specs sobre UN solo aviso
=============================================================================

POR QUÉ ESTE PASO:
  Antes de tirarle a 45.000 avisos, hay que confirmar que el extractor funciona
  contra el sitio real. Esta prueba con UN aviso responde dos cosas a la vez:
    - ¿Los specs están en el HTML?  (si devuelve datos -> SÍ, caso B)
    - ¿El parser los agarra bien?    (los imprime para que los revises)
  Si NO devuelve nada, los specs vienen de una API aparte (caso A) y hay que
  cazar ese endpoint con F12 > Network (ver nota al final de especificaciones.py).

CÓMO USARLO:
  1. Cambiá la URL de abajo por la de cualquier aviso real de Chileautos.
  2. Corré:  python probar_especificaciones.py
  3. Mirá lo que imprime.
"""

import asyncio
import sys
from curl_cffi.requests import AsyncSession
from especificaciones import extract_specs, parsear_especificaciones, headers_base

# 👇 PEGÁ ACÁ LA URL DE UN AVISO REAL (el del Sedán 1.5 que mandaste, u otro)
URL_PRUEBA = "https://www.chileautos.cl/vehiculos/detalles/2022-peugeot-3008-1-5-bluehdi-130-auto-gt/CP-AD-8511086"


async def main():
    print(f"Probando extracción de specs sobre:\n  {URL_PRUEBA}\n")
    async with AsyncSession() as session:
        # Primero bajamos el HTML crudo para inspeccionar
        try:
            resp = await session.get(
                URL_PRUEBA, headers=headers_base,
                impersonate="chrome99_android", timeout=10
            )
        except Exception as e:
            print(f"❌ No se pudo bajar la página: {e}")
            return

        print(f"Status HTTP: {resp.status_code}")
        if resp.status_code != 200:
            print("La página no respondió 200. Si es 403/429 es bloqueo de Datadome.")
            return

        html = resp.text
        print(f"Tamaño del HTML: {len(html):,} caracteres\n")

        # Chequeo directo: ¿está el número 2550 (distancia entre ejes) en el HTML?
        # Esto responde la pregunta del Ctrl+U de forma automática.
        for marcador in ("2550", "Distancia entre ejes", "Cilindrada exacta"):
            esta = marcador in html
            print(f"  '{marcador}' en el HTML: {'SÍ ✅' if esta else 'NO ❌'}")
        print()

        limpios, crudos = parsear_especificaciones(html)

        if not crudos:
            print("⚠️  No se halló NINGÚN par etiqueta/valor en el HTML.")
            print("    => Los specs probablemente vienen de una API aparte (caso A).")
            print("    => Hay que cazar el endpoint con F12 > Network.")
            return

        print(f"Pares etiqueta/valor hallados en total: {len(crudos)}")
        print(f"Specs clave mapeados: {len(limpios)}\n")

        print("--- SPECS CLAVE (los que sirven para agrupar versiones) ---")
        for k in ("version_oficial", "cilindrada_cc", "cilindrada", "power_hp",
                  "torque_nm", "carroceria", "traccion_spec", "transmision_spec",
                  "tipo_caja", "combustible_spec", "puertas", "asientos"):
            print(f"  {k:18s}: {limpios.get(k, '(no vino)')}")

        print("\n--- TODOS los pares crudos (para revisar) ---")
        for etiqueta, valor in sorted(crudos.items()):
            print(f"  {etiqueta:35s} -> {valor}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
