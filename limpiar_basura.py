# -*- coding: utf-8 -*-
"""Limpieza segura de la carpeta. Correr:  python limpiar_basura.py
Borra SOLO basura conocida (fragmentos de código pegado en cmd y debug
viejo), nombre por nombre. NO toca datos, scripts ni respaldos."""
import os

BASURA = [
    # fragmentos creados al pegar codigo en la ventana negra
    "'1.5", "'1.5'", "'1.6", "'2.0'", "'5.0'", "0", "0)", "0.40", "1", "10",
    "10)", "12].copy()", "15]", "1]", "2", "2.0", "3", "35%", "3]", "5",
    "55%)", "6]", "8%", "85%", "ANIO", "DESCUENTO_MAX_CREIBLE",
    "DESCUENTO_MIN)", "MIN_COMPARABLES]", "NO", "None", "escribe", "fija",
    "git", "lo", "lo)", "main", "marca", "nunca", "oro", "python",
    "revisar", "se", "2026-07-08",
    # debug viejo del scraper de fichas
    "specs_debug_1.html", "specs_debug_2.html", "specs_debug_3.html",
    "specs_debug_4.html",
    # parche ya aplicado (el .bak del incremental se conserva)
    "arreglar_incremental.py",
]

borrados, no_estaban = 0, 0
for nombre in BASURA:
    if os.path.isfile(nombre):
        try:
            os.remove(nombre)
            print(f"borrado: {nombre}")
            borrados += 1
        except Exception as e:
            print(f"no pude borrar {nombre}: {e}")
    else:
        no_estaban += 1

print("-" * 40)
print(f"Listo: {borrados} archivos basura borrados "
      f"({no_estaban} de la lista ya no estaban).")
print("Todo lo demás quedó intacto.")
