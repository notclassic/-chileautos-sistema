#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SUBIR A GITHUB - sube los resultados al repositorio
====================================================
Sube datos.json (y dashboard.html si cambio) a GitHub con un commit
automatico. Pensado para correr al final del flujo, sin tocar GitHub Desktop.

Uso:
    python subir_github.py

Requiere: Git instalado y el repositorio ya clonado (esta carpeta).
NO sube las capturas Excel (las excluye el .gitignore).
"""

import subprocess, sys, os
from datetime import datetime


def git(*args):
    """Corre un comando git y devuelve (ok, salida)."""
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def main():
    if not os.path.isdir(".git"):
        sys.exit("Esta carpeta no es un repositorio Git. Corre esto dentro de "
                 "la carpeta del repo (-chileautos-sistema).")

    # 1. Agregar los archivos de resultados
    git("add", "datos.json")
    git("add", "dashboard.html")

    # 2. Ver si hay algo nuevo para subir
    ok, salida = git("status", "--porcelain")
    if not salida:
        print("[github] No hay cambios para subir. Todo al dia.")
        return

    # 3. Commit con fecha
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    ok, out = git("commit", "-m", f"Actualizo datos {fecha}")
    if not ok:
        print("[github] No se pudo hacer commit:\n", out)
        return
    print(f"[github] Commit hecho: {fecha}")

    # 4. Subir a GitHub
    ok, out = git("push")
    if ok:
        print("[github] Subido a GitHub correctamente.")
    else:
        print("[github] No se pudo subir (push). Detalle:\n", out)
        print("[github] Si pide usuario/clave, abri GitHub Desktop una vez "
              "para que quede la sesion guardada, y volve a intentar.")


if __name__ == "__main__":
    main()
