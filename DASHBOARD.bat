@echo off
cd /d "%~dp0"
rem Arranca el panel en segundo plano (minimizado); si ya corre, la ventana se cierra sola
start "Panel Chileautos" /min cmd /c "python panel.py --silencioso"
rem Abre el dashboard
start "" dashboard.html
