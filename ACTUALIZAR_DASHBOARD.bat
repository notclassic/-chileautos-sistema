@echo off
REM ============================================================
REM  ACTUALIZAR DASHBOARD - doble clic para correr todo
REM ============================================================
REM  Este archivo corre el sistema y actualiza el dashboard online.
REM  Doble clic y listo. No hay que escribir nada.
REM
REM  IMPORTANTE: este archivo tiene que estar DENTRO de la carpeta
REM  del repositorio (-chileautos-sistema), o apuntar a ella abajo.
REM ============================================================

REM -- Ir a la carpeta del proyecto (ajusta la ruta si la moviste) --
cd /d "%~dp0"

echo.
echo ====================================================
echo   ACTUALIZANDO DASHBOARD DE CHILEAUTOS
echo   Esto tarda unos minutos. No cierres la ventana.
echo ====================================================
echo.

python ver_comentarios.py

echo.
echo ====================================================
echo   LISTO. El dashboard online se actualiza en 1-2 min:
echo   https://notclassic.github.io/-chileautos-sistema/dashboard.html
echo ====================================================
echo.
pause
