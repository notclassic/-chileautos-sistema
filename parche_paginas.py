# -*- coding: utf-8 -*-
"""Parche del limite de paginas. Correr:  python parche_paginas.py
Convierte el limite fijo de 20 paginas de actualizar_incremental.py en uno
configurable: CATALOGO COMPLETO (3000 paginas) en TODAS las bajadas. Deja respaldo."""
import os
import py_compile
import re
import shutil

ARCHIVO = 'actualizar_incremental.py'
if not os.path.exists(ARCHIVO):
    print(f"No encuentro {ARCHIVO}. Corre esto en la carpeta del sistema.")
    raise SystemExit(1)

src = open(ARCHIVO, encoding='utf-8', errors='replace').read()

if "CA_PAGINAS" in src:
    if "'300'" in src:
        src = src.replace("os.environ.get('CA_PAGINAS', '300')",
                          "os.environ.get('CA_PAGINAS', '3000')")
        open(ARCHIVO, 'w', encoding='utf-8').write(src)
        print("Actualizado: de 300 a catalogo COMPLETO (3000) en todas las bajadas.")
    else:
        print("Ya estaba en catalogo completo. Nada que hacer.")
    raise SystemExit(0)

# buscar la asignacion del limite de paginas con valor 20
patrones = [
    r'(?m)^(\s*)([A-Za-z_]*[Pp][AaÁá]?[Gg][A-Za-z_]*)\s*=\s*20\b',
]
candidatos = []
for pat in patrones:
    candidatos += [(m.group(1), m.group(2), m.start()) for m in re.finditer(pat, src)]

if len(candidatos) != 1:
    print(f"No pude identificar la linea con certeza ({len(candidatos)} candidatas).")
    print("Lineas del archivo que mencionan paginas o el valor 20:")
    for i, lin in enumerate(src.splitlines(), 1):
        low = lin.lower()
        if ('pagin' in low or 'page' in low) and ('20' in lin or '=' in lin):
            print(f"  {i}: {lin.rstrip()[:90]}")
    print("Pega esas lineas en el chat para un parche a medida.")
    raise SystemExit(0)

indent, nombre, pos = candidatos[0]
shutil.copy2(ARCHIVO, ARCHIVO + '.bak2')
viejo = re.search(r'(?m)^' + re.escape(indent + nombre) + r'\s*=\s*20\b.*$', src).group(0)
nuevo = (f"{indent}{nombre} = int(os.environ.get('CA_PAGINAS', '3000'))"
         f"  # paginas del catalogo: SIEMPRE completo")
src = src.replace(viejo, nuevo, 1)
if not re.search(r'(?m)^import os\b', src):
    src = "import os\n" + src

open(ARCHIVO, 'w', encoding='utf-8').write(src)
try:
    py_compile.compile(ARCHIVO, doraise=True)
except py_compile.PyCompileError as e:
    shutil.copy2(ARCHIVO + '.bak2', ARCHIVO)
    print("Fallo al compilar; restaure el original.")
    print(str(e)[:200])
    raise SystemExit(1)

print(f"Listo: '{nombre} = 20' eliminado. TODAS las bajadas leen el catalogo completo.")
print("Cada 'Bajar base' tomara 2-4 horas y captura los 44.000+ avisos.")
