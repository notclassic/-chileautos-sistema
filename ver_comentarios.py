# -*- coding: utf-8 -*-
"""
ver_comentarios.py — clasifica comentarios, corre el motor y arma dashboard.html
Con AUTODIAGNÓSTICO: imprime qué plantilla usa y verifica que el dashboard
quede con los cambios. Si algo se corta, este script lo dice.
"""
import os
import subprocess
import sys
from datetime import datetime

CARPETA = os.path.dirname(os.path.abspath(__file__))
os.chdir(CARPETA)

PLANTILLA = "plantilla_dashboard.html"
DATOS = "datos.json"
SALIDA = "dashboard.html"
# Marcadores de los cambios recientes: si la plantilla los tiene, el dashboard
# final también debe tenerlos. Sirve para detectar plantillas viejas.
MARCADORES = ["renderFiltrosComp", "msort", "abrirSelectorVersion", "dbInit"]


def paso(titulo):
    print(f"\n========== {titulo} ==========")


def correr(script):
    """Corre un script python y devuelve True si terminó bien."""
    if not os.path.exists(script):
        print(f"[ver] (no existe {script}, salteo)")
        return True
    r = subprocess.run([sys.executable, script])
    if r.returncode != 0:
        print(f"[ver] FALLO {script} (código {r.returncode}).")
        return False
    return True


def main():
    paso("PASO 1 - CLASIFICAR COMENTARIOS")
    if not correr("clasificar_comentarios.py"):
        print("[ver] (sigo igual: uso la clasificación anterior)")

    paso("PASO 2 - MOTOR")
    if not correr("motor.py"):
        sys.exit(1)

    paso("PASO 3 - ARMAR DASHBOARD (con control)")
    # --- CONTROL 0: el motor y los archivos de datos son los correctos ---
    if os.path.exists("motor.py"):
        motor_src = open("motor.py", encoding="utf-8", errors="replace").read()
        mt_motor = datetime.fromtimestamp(os.path.getmtime("motor.py"))
        print(f"[control] motor.py: {len(motor_src):,} caracteres | "
              f"modificado {mt_motor:%Y-%m-%d %H:%M}")
        for marca, desc in [("DEP_ANIO", "ajuste por año+km"),
                            ("descuento_extremo", "marcado de descuentos altos"),
                            ("Generaciones asignadas", "asignación de generaciones"),
                            ("_comp_estricto", "coherencia radar-modal"),
                            ("depuracion_avisos", "tabla de Depuración BBDD"),
                            ("_VOF_PERFIL", "sugeridas unificadas con ficha"),
                            ("cab.simple", "cabinas en versiones (rc/reg/super cab)"),
                            ("_MOTOR_DOM", "herencia de motor dominante"),
                            ("_CONSOLIDA", "consolidación de versiones")]:
            tiene = marca in motor_src
            print(f"[control]   {'SI' if tiene else 'NO'} tiene {desc}"
                  + ("" if tiene else "   <-- MOTOR VIEJO: reemplazalo con el último"))
    if os.path.exists("generaciones.xlsx"):
        print(f"[control] generaciones.xlsx: existe "
              f"({os.path.getsize('generaciones.xlsx'):,} bytes)")
    else:
        print("[control] generaciones.xlsx: NO EXISTE   <-- sin este archivo "
              "TODAS las generaciones salen vacías ('—'). Ponelo en la carpeta.")
    if os.path.exists("especificaciones.csv"):
        print(f"[control] especificaciones.csv: existe "
              f"({os.path.getsize('especificaciones.csv'):,} bytes)")
    else:
        print("[control] especificaciones.csv: no existe (la columna 'Sugerida "
              "(ficha)' saldrá vacía)")

    # --- CONTROL 1: la plantilla existe y qué tiene adentro ---
    if not os.path.exists(PLANTILLA):
        sys.exit(f"[ver] NO existe {PLANTILLA} en {CARPETA}. No puedo armar nada.")
    plantilla = open(PLANTILLA, encoding="utf-8").read()
    mtime = datetime.fromtimestamp(os.path.getmtime(PLANTILLA))
    print(f"[control] plantilla: {PLANTILLA} | {len(plantilla):,} caracteres | "
          f"modificada {mtime:%Y-%m-%d %H:%M}")
    for m in MARCADORES:
        tiene = m in plantilla
        print(f"[control]   {'SI' if tiene else 'NO'} tiene '{m}'"
              + ("" if tiene else "   <-- PLANTILLA VIEJA: reemplazala con la última"))
    if "/*__DATA__*/" not in plantilla:
        sys.exit("[ver] La plantilla no tiene el hueco /*__DATA__*/. Está rota o "
                 "no es la plantilla del dashboard.")

    # --- CONTROL 2: datos.json fresco ---
    if not os.path.exists(DATOS):
        sys.exit(f"[ver] No existe {DATOS}. El motor no lo generó.")
    dt_datos = datetime.fromtimestamp(os.path.getmtime(DATOS))
    print(f"[control] datos.json: modificado {dt_datos:%Y-%m-%d %H:%M} "
          f"({os.path.getsize(DATOS)/1e6:.1f} MB)")

    datos = open(DATOS, encoding="utf-8").read()
    html = plantilla.replace("/*__DATA__*/", "const DATA = " + datos + ";")

    tmp = SALIDA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)
    os.replace(tmp, SALIDA)

    # --- CONTROL 3: el dashboard final tiene los cambios ---
    ok = all(m in html for m in MARCADORES)
    dt_dash = datetime.fromtimestamp(os.path.getmtime(SALIDA))
    print(f"[control] dashboard.html escrito: {dt_dash:%Y-%m-%d %H:%M} "
          f"({os.path.getsize(SALIDA)/1e6:.1f} MB)")
    if ok:
        print("[control] ✔ el dashboard TIENE los cambios nuevos (filtros, "
              "orden, selector). Ctrl+F5 en Chrome y deberías verlos.")
    else:
        print("[control] ✖ el dashboard NO tiene los cambios. La plantilla de "
              "esta carpeta es vieja: reemplazala con la última y corré de nuevo.")
    print("[ver] dashboard armado.")

    paso("PASO 4 - SUBIR A GITHUB")
    try:
        subprocess.run(["git", "add", SALIDA, DATOS], check=False)
        subprocess.run(["git", "commit", "-m",
                        f"Comentarios {datetime.now():%Y-%m-%d %H:%M}"], check=False)
        r = subprocess.run(["git", "push"], capture_output=True, text=True)
        if r.returncode != 0:
            print("[ver] No se pudo subir:\n", (r.stderr or r.stdout)[-500:])
            print("[ver] Si dice 'rejected', corré: git pull   y despues   git push")
    except Exception as e:
        print(f"[ver] (git no disponible: {e})")


if __name__ == "__main__":
    main()
