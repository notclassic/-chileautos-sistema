@echo off
REM ============================================================
REM  DESCARGAR BASE - doble clic para traer autos nuevos
REM ============================================================
REM  Corre el scraper, baja autos de Chileautos, los guarda en
REM  capturas/, recalcula y sube el dashboard.
REM  Doble clic y listo.
REM ============================================================

cd /d "%~dp0"

echo.
echo ====================================================
echo   DESCARGANDO BASE NUEVA DE CHILEAUTOS
echo   Esto puede tardar varios minutos. No cierres la ventana.
echo ====================================================
echo.

python actualizar.py

echo.
echo ====================================================
echo   LISTO. El dashboard online se actualiza en 1-2 min:
echo   https://notclassic.github.io/-chileautos-sistema/dashboard.html
echo ====================================================
echo.
pause
