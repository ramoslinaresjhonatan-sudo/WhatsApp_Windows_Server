@echo off
title WhatsApp Bot - Lanzador Automático
color 0b
echo ==========================================
echo    INICIANDO PUENTE WHATSAPP PROFESIONAL
echo ==========================================
echo.

:: 1. Activar el entorno virtual
echo [+] Activando entorno virtual...
call venv\Scripts\activate

:: 2. Iniciar el Guardián del Navegador en segundo plano
echo [+] Iniciando Guardián del Navegador...
start /b python Scripts\Src\VentaDeWhatsapp.py

:: 3. Esperar unos segundos para que el navegador abra
timeout /t 5 >nul

:: 4. Iniciar el Puente API en segundo plano
echo [+] Iniciando Puente API (FastAPI)...
start /b python Scripts\Src\ApiPuenteWhatsApp.py

echo.
echo ==========================================
echo    TODO LISTO - EL BOT ESTA CORRIENDO
echo ==========================================
echo.
pause
