@echo off
title WhatsApp Bot - Instalador Profesional
color 0a
echo    CONFIGURANDO ENTORNO WHATSAPP
if not exist "venv" (
    echo [+] Creando entorno virtual Python (venv)...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [!] ERROR: Python no esta instalado o no esta en el PATH.
        pause
        exit /b
    )
) else (
    echo [ok] El entorno virtual ya existe.
)

echo [+] Activando entorno virtual...
call venv\Scripts\activate

echo [+] Actualizando pip...
python -m pip install --upgrade pip

echo [+] Instalando dependencias desde requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [!] ERROR al instalar dependencias. Revisa tu conexion a internet.
    pause
    exit /b
)

echo [+] Instalando motores de navegacion (Playwright)...
playwright install msedge
if %errorlevel% neq 0 (
    echo [!] ERROR al instalar motores de Playwright.
    pause
    exit /b
)


echo    PREPARANDO SESION DE WHATSAPP
echo [+] Abriendo navegador para escanear QR...
echo [!] IMPORTANTE: Escanea el QR y espera a que carguen tus chats.
echo [!] Una vez cargados, cierra el navegador para finalizar el setup.
echo.
python Scripts\Util\Login.py
echo ==========================================
echo Ya puedes ejecutar INICIAR_TODO.bat
echo.
pause
