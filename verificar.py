# -*- coding: utf-8 -*-
"""Verificador del sistema Chileautos. Correr:  python verificar.py
Imprime un reporte corto: pegalo COMPLETO en el chat."""
import os
import subprocess
import sys

print("=" * 52)
print("VERIFICADOR CHILEAUTOS")
print("=" * 52)

def firma(nombre):
    if not os.path.exists(nombre):
        return None
    return len(open(nombre, encoding='utf-8', errors='replace').read())

esperados = {
    'motor.py': 131588,
    'plantilla_dashboard.html': 144848,
    'ver_comentarios.py': 6087,
    'panel.py': 28853,
    'clasificar_ia.py': 7050,
    'scrapper.py': 25836,
}
for f, esp in esperados.items():
    real = firma(f)
    if real is None:
        print(f"FALTA   {f}")
    elif real == esp:
        print(f"OK      {f}  ({real:,})".replace(',', '.'))
    else:
        print(f"VIEJO   {f}  tiene {real:,} / esperado {esp:,}".replace(',', '.'))

m = open('motor.py', encoding='utf-8', errors='replace').read() if os.path.exists('motor.py') else ''
print("blindaje url en motor:", "SI" if "if 'url' not in df.columns" in m else "NO")

print("-" * 52)
print("Corriendo el motor (puede tardar 1-2 min)...")
r = subprocess.run([sys.executable, 'motor.py'], capture_output=True, text=True)
if r.returncode == 0:
    print("MOTOR: OK, termino sin errores.")
    for lin in r.stdout.splitlines()[-3:]:
        print("  " + lin)
else:
    print("MOTOR: FALLO. Ultimas lineas del error:")
    err = (r.stderr or r.stdout).splitlines()
    for lin in err[-15:]:
        print("  " + lin)
print("=" * 52)
print("Pega TODO este reporte en el chat.")
