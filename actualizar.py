#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ACTUALIZAR - comando unico que deja el dashboard online al dia
==============================================================
Hace todo de corrido:
  1. (opcional) corre el scraper para traer autos nuevos
  2. corre el motor (oportunidades + rotacion) -> datos.json
  3. incrusta los datos dentro de dashboard.html (para que funcione online)
  4. sube datos.json y dashboard.html a GitHub

Uso:
    python actualizar.py                -> scraper + motor + dashboard + subir
    python actualizar.py --solo-motor   -> salta el scraper (recalcula y sube)

Requiere: los archivos del proyecto + plantilla_dashboard.html en la carpeta.
"""

import sys, os, json, subprocess, shutil
from datetime import datetime


def log(m):
    print(f"\n========== {m} ==========\n", flush=True)


def run(*args):
    return subprocess.run([sys.executable, *args]).returncode == 0


# ---------------------------------------------------------------------------
def correr_scraper():
    if not os.path.exists("scrapper_auto.py") or not os.path.exists("main.py"):
        print("[actualizar] Falta scrapper_auto.py o main.py, salto el scraper.")
        return False
    habia = os.path.exists("scrapper.py")
    if habia:
        os.replace("scrapper.py", "scrapper_original_backup.py")
    shutil.copy("scrapper_auto.py", "scrapper.py")
    try:
        log("PASO 1 - SCRAPER")
        ok = run("main.py")
    finally:
        if os.path.exists("scrapper.py"):
            os.remove("scrapper.py")
        if habia:
            os.replace("scrapper_original_backup.py", "scrapper.py")
    return ok


def correr_motor():
    log("PASO 2 - MOTOR")
    return run("motor.py")


def incrustar_datos():
    """Mete datos.json dentro del dashboard, usando plantilla_dashboard.html."""
    log("PASO 3 - ARMAR DASHBOARD")
    if not os.path.exists("datos.json"):
        print("[actualizar] No hay datos.json. Aborto.")
        return False
    # La plantilla es el dashboard con el hueco /*__DATA__*/ sin rellenar.
    # Si no existe plantilla, intentamos usar dashboard.html como plantilla
    # (solo sirve la 1a vez; despues conviene tener plantilla_dashboard.html).
    fuente = "plantilla_dashboard.html" if os.path.exists("plantilla_dashboard.html") else "dashboard.html"
    tpl = open(fuente, encoding="utf-8").read()
    if "/*__DATA__*/" not in tpl:
        print("[actualizar] La plantilla no tiene el hueco /*__DATA__*/.")
        print("[actualizar] Asegurate de tener plantilla_dashboard.html con ese hueco.")
        return False
    d = json.load(open("datos.json", encoding="utf-8"))
    data_js = "const DATA = " + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + ";"
    out = tpl.replace("/*__DATA__*/", data_js)
    open("dashboard.html", "w", encoding="utf-8").write(out)
    print("[actualizar] dashboard.html armado con los datos del", d.get("captura_analizada", "?"))
    return True


def subir_github():
    log("PASO 4 - SUBIR A GITHUB")
    if not os.path.isdir(".git"):
        print("[actualizar] Esta carpeta no es un repo Git. No subo.")
        return False
    subprocess.run(["git", "add", "datos.json", "dashboard.html"])
    r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if not r.stdout.strip():
        print("[actualizar] No hay cambios para subir.")
        return True
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    subprocess.run(["git", "commit", "-m", f"Actualizo {fecha}"])
    r = subprocess.run(["git", "push"], capture_output=True, text=True)
    if r.returncode == 0:
        print("[actualizar] Subido a GitHub. El dashboard online se actualiza en 1-2 min.")
        return True
    print("[actualizar] No se pudo subir:\n", (r.stdout + r.stderr).strip())
    return False


def main():
    solo_motor = "--solo-motor" in sys.argv
    if not solo_motor:
        correr_scraper()
    if not correr_motor():
        sys.exit("Fallo el motor.")
    if not incrustar_datos():
        sys.exit("Fallo al armar el dashboard.")
    subir_github()
    log("LISTO")
    print("Dashboard online: https://notclassic.github.io/-chileautos-sistema/dashboard.html")


if __name__ == "__main__":
    main()
