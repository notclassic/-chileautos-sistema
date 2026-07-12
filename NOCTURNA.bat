@echo off
rem NOCTURNA.bat - bajada COMPLETA del catalogo (3000 paginas) + cadena entera.
rem Para programarla automatica cada noche a las 02:30, correr UNA Vez en cmd:
rem   schtasks /create /tn ChileautosNocturna /tr "\"%~dp0NOCTURNA.bat\"" /sc daily /st 02:30
cd /d "%~dp0"
set CA_PAGINAS=3000
python marcar.py inicio
python actualizar_incremental.py && python enriquecer_comentarios.py --solo-nuevos && python bajar_especificaciones.py --solo-nuevos --limite 0 && python relleno_condicional.py && python clasificar_ia.py && python ver_comentarios.py
python marcar.py fin
