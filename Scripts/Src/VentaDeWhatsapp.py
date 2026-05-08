import sys
import asyncio
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

from dotenv import load_dotenv
load_dotenv(_BASE_DIR / ".env")

from Scripts.Util.Logger import setup_logger
from Scripts.Util.BrowserManager import BrowserManager

logger = setup_logger("WhatsApp-Browser", "whatsapp.log")


async def run() -> None:
    logger.info("=== WhatsApp Guardian Service starting ===")
    manager = BrowserManager()
    try:
        await manager.launch_and_maintain("https://web.whatsapp.com")
    except Exception as exc:
        logger.exception("Critical service failure: %s", exc)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Service stopped by user.")