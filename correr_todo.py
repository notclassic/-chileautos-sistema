#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FLUJO UNICO - Chileautos
Corre scraper + motor con un solo comando.
  python correr_todo.py              -> scraper + motor
  python correr_todo.py --solo-motor -> salta el scraper
Requiere en la misma carpeta: scrapper_auto.py, main.py, telefono.py, nombreWHAPP.py, motor.py
"""

import sys, time, subprocess, os


def log(m):
    print(f"\n========== {m} ==========\n", flush=True)


def correr_scraper():
    if not os.path.exists("scrapper_auto.py"):
        sys.exit("Falta scrapper_auto.py")
    if not os.path.exists("main.py"):
        sys.exit("Falta main.py")

    habia_original = os.path.exists("scrapper.py")
    if habia_original:
        os.replace("scrapper.py", "scrapper_original_backup.py")
    import shutil
    shutil.copy("scrapper_auto.py", "scrapper.py")

    try:
        log("PASO 1/2 - SCRAPER (puede tardar)")
        res = subprocess.run([sys.executable, "main.py"])
        if res.returncode != 0:
            print("[flujo] El scraper termino con error.")
            return False
        return True
    finally:
        os.remove("scrapper.py")
        if habia_original:
            os.replace("scrapper_original_backup.py", "scrapper.py")


def correr_motor():
    if not os.path.exists("motor.py"):
        sys.exit("Falta motor.py")
    log("PASO 2/2 - MOTOR")
    res = subprocess.run([sys.executable, "motor.py"])
    return res.returncode == 0


def main():
    solo_motor = "--solo-motor" in sys.argv
    inicio = time.time()
    if not solo_motor:
        if not correr_scraper():
            sys.exit("Se detuvo en el scraper.")
    else:
        log("Modo --solo-motor: salto el scraper")
    if not correr_motor():
        sys.exit("Se detuvo en el motor.")
    mins = (time.time() - inicio) / 60
    log(f"FLUJO COMPLETO en {mins:.1f} minutos")
    print("Listo: datos.json actualizado.")


if __name__ == "__main__":
    main()