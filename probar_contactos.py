# -*- coding: utf-8 -*-
"""
probar_contactos.py — Prueba teléfono + specs sobre unos pocos avisos reales.

Responde una sola pregunta: ¿podemos hoy bajar teléfono y especificaciones
de un aviso, con el sistema tal como está? Prueba 3 avisos (distintos tipos:
CP-AD, GI-AD) e imprime qué trae cada uno.

Correr:  python probar_contactos.py
"""

import asyncio
import sys
from curl_cffi.requests import AsyncSession

from telefono import extract_phone_fast
from especificaciones import extract_specs

# Avisos reales de la última corrida (URL verdadera, no el texto del Excel)
URLS_PRUEBA = [
    "https://www.chileautos.cl/vehiculos/detalles/2018-bmw-x1-bmw-x1-sdrive-20i-2-0/CP-AD-8532255",
    "https://www.chileautos.cl/vehiculos/detalles/toyota-land-cruiser-prado-tx-2013/GI-AD-913507",
    "https://www.chileautos.cl/vehiculos/detalles/2011-bmw-316-i/CP-AD-8530251",
]


async def main():
    async with AsyncSession() as session:
        for i, url in enumerate(URLS_PRUEBA, 1):
            print(f"\n===== Aviso {i}/{len(URLS_PRUEBA)} =====")
            print(url)

            # 1) Teléfono / WhatsApp
            print("\n-- Contacto (telefono.py) --")
            try:
                contacts = await extract_phone_fast(url, session)
                if contacts:
                    print(f"   telefono: {contacts.get('telefono')}")
                    print(f"   whatsapp: {contacts.get('whatsapp')}")
                    if not contacts.get('telefono') and not contacts.get('whatsapp'):
                        print("   (respondió, pero sin teléfono ni whatsapp en el aviso)")
                else:
                    print("   NADA. La API no devolvió datos (posible bloqueo 403/429).")
            except Exception as e:
                print(f"   ERROR: {e}")

            # 2) Especificaciones
            print("\n-- Especificaciones (especificaciones.py) --")
            try:
                specs = await extract_specs(url, session)
                if specs:
                    print(f"   version_oficial: {specs.get('version_oficial')}")
                    print(f"   cilindrada_cc:   {specs.get('cilindrada_cc')}")
                    print(f"   power_hp:        {specs.get('power_hp')}")
                    print(f"   traccion_spec:   {specs.get('traccion_spec')}")
                    print(f"   (total campos: {len(specs)})")
                else:
                    print("   NADA. La página no devolvió specs (bloqueo o estructura distinta).")
            except Exception as e:
                print(f"   ERROR: {e}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
