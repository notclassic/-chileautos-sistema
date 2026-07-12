@echo off
REM ============================================================
REM  PROBAR.bat - Prueba manual. La ventana NO se cierra al final.
REM ============================================================
cd /d "%~dp0"

echo. > log_actualizacion.txt
echo ======== INICIO %date% %time% ======== >> log_actualizacion.txt

echo Corriendo datos incrementales (prueba)...
echo [1/2] Datos incrementales... >> log_actualizacion.txt
python actualizar_incremental.py >> log_actualizacion.txt 2>&1

echo Corriendo motor + dashboard + GitHub...
echo [2/2] Motor + dashboard + GitHub... >> log_actualizacion.txt
python actualizar.py --solo-motor >> log_actualizacion.txt 2>&1

echo ======== FIN %date% %time% ======== >> log_actualizacion.txt

echo.
echo ============================================
echo   TERMINO. Revisa arriba si hubo errores.
echo   El detalle quedo en log_actualizacion.txt
echo ============================================
echo.
pause
