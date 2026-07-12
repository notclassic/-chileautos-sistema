@echo off
rem Corrida automatica: base + descripciones nuevos + specs nuevos + dashboard
cd /d "%~dp0"
echo ======== INICIO %date% %time% ======== >> log_actualizacion.txt
python actualizar_incremental.py >> log_actualizacion.txt 2>&1
python enriquecer_comentarios.py --solo-nuevos >> log_actualizacion.txt 2>&1
python bajar_especificaciones.py --solo-nuevos --limite 0 >> log_actualizacion.txt 2>&1
python enriquecer_comentarios.py --limite 150 >> log_actualizacion.txt 2>&1
python bajar_especificaciones.py --limite 150 >> log_actualizacion.txt 2>&1
python ver_comentarios.py >> log_actualizacion.txt 2>&1
echo ======== FIN %date% %time% ======== >> log_actualizacion.txt
