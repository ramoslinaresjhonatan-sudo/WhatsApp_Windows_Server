import os
import sys
import asyncio
from dotenv import load_dotenv

DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(DIRECTORIO_ACTUAL))
util_path = os.path.join(os.path.dirname(DIRECTORIO_ACTUAL), "Util")

if util_path not in sys.path:
    sys.path.insert(0, util_path)
try:
    from Logger import setup_logger
    from BrowserManager import BrowserManager
except ImportError as e:
    print(f"Error crítico al importar utilidades: {e}")
    sys.exit(1)

load_dotenv(os.path.join(BASE_DIR, '.env'))

logger = setup_logger("WhatsApp-Browser", "whatsapp.log")

async def iniciar_servicio():
    try:
        puerto = os.getenv("PUERTO_WHATSAPP", "9222")
        user_data = os.path.join(BASE_DIR, 'Storage', 'sesion_whatsapp')
        headless = os.getenv("MODO_HEADLESS", "False").lower() == "true"
        
        manager = BrowserManager(
            user_data_dir=user_data,
            puerto=puerto,
            headless=headless
        )

        logger.info("--- Iniciando Servicio Guardián de WhatsApp (Async) ---")
        await manager.lanzar_y_mantener("https://web.whatsapp.com")

    except Exception as e:
        logger.error(f"Fallo crítico en el servicio: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(iniciar_servicio())
    except KeyboardInterrupt:
        logger.info("Servicio detenido por el usuario.")