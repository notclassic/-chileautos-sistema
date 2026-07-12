@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  ARREGLAR: instalar ultima plantilla + regenerar + abrir
echo ============================================

rem 1) tomar la plantilla_dashboard*.html MAS RECIENTE de Descargas
set "ULT="
for /f "delims=" %%f in ('dir /b /o-d "%USERPROFILE%\Downloads\plantilla_dashboard*.html" 2^>nul') do (
    if not defined ULT set "ULT=%%f"
)
if defined ULT (
    copy /y "%USERPROFILE%\Downloads\%ULT%" "plantilla_dashboard.html" >nul
    echo [1/3] Instalada desde Descargas: %ULT%
) else (
    echo [1/3] No hay plantillas en Descargas: uso la que ya esta en la carpeta.
)

rem 2) regenerar el dashboard con esa plantilla
echo [2/3] Regenerando (1-3 minutos)...
python ver_comentarios.py

rem 3) abrir el dashboard recien construido
echo [3/3] Abriendo el dashboard...
start "" "dashboard.html"
echo.
echo LISTO. En el dashboard, arriba a la derecha debe decir: plantilla v6
pause
