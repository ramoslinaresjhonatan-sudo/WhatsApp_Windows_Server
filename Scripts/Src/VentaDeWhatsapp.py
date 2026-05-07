import os
import sys
import asyncio
from dotenv import load_dotenv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(CURRENT_DIR))
util_path = os.path.join(os.path.dirname(CURRENT_DIR), "Util")

if util_path not in sys.path:
    sys.path.insert(0, util_path)
try:
    # pyrefly: ignore [missing-import]
    from Logger import setup_logger
    # pyrefly: ignore [missing-import]
    from BrowserManager import BrowserManager
except ImportError as e:
    sys.exit(1)

load_dotenv(os.path.join(BASE_DIR, '.env'))

logger = setup_logger("WhatsApp-Browser", "whatsapp.log")

async def start_service():
    try:
        port = os.getenv("PUERTO_WHATSAPP", "9222")
        user_data = os.path.join(BASE_DIR, 'Storage', 'sesion_whatsapp')
        headless = os.getenv("MODO_HEADLESS", "False").lower() == "true"
        
        manager = BrowserManager(
            user_data_dir=user_data,
            port=port,
            headless=headless
        )

        logger.info("--- Starting WhatsApp Guardian Service (Async) ---")
        await manager.launch_and_maintain("https://web.whatsapp.com")

    except Exception as e:
        logger.error(f"Critical service failure: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(start_service())
    except KeyboardInterrupt:
        pass