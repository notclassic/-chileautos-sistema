# -*- coding: utf-8 -*-
"""
marcar.py — Deja registro de cuándo empieza y termina una corrida de base.
Lo usan los comandos del panel; el dashboard lee estos archivos para mostrar
"Base bajando..." / "Última base descargada: ...".
Uso interno:  python marcar.py inicio | fin
"""
import os
import sys
from datetime import datetime

FLAG = "corrida_en_curso.txt"
ULTIMA = "ultima_base.txt"

ahora = datetime.now().strftime("%d-%m-%Y %H:%M")
if len(sys.argv) > 1 and sys.argv[1] == "inicio":
    with open(FLAG, "w", encoding="utf-8") as f:
        f.write(ahora)
elif len(sys.argv) > 1 and sys.argv[1] == "fin":
    with open(ULTIMA, "w", encoding="utf-8") as f:
        f.write(ahora)
    if os.path.exists(FLAG):
        os.remove(FLAG)
