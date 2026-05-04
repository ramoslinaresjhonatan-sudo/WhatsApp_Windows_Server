import os
import sys
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

def iniciar_servicio():
    try:
        puerto = os.getenv("PUERTO_WHATSAPP")
        user_data = os.path.join(BASE_DIR, 'Storage', 'sesion_whatsapp')
        limite_ram = int(os.getenv("LIMITE_RAM_MB", "400"))
        headless = os.getenv("MODO_HEADLESS", "False").lower() == "true"
        browser = BrowserManager(
            user_data_dir=user_data,
            puerto=puerto,
            headless=headless,
            limite_ram_mb=limite_ram
        )

        logger.info("--- Iniciando Servicio Guardián de WhatsApp ---")
        browser.lanzar_y_mantener("https://web.whatsapp.com")

    except Exception as e:
        logger.error(f"Fallo crítico en el servicio: {e}")

if __name__ == "__main__":
    iniciar_servicio()