import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class AppConfig:
    BASE_DIR: Path = BASE_DIR
    LOG_DIR: Path = BASE_DIR / "Logs"
    STORAGE_DIR: Path = BASE_DIR / "Storage"
    SESSION_DIR: Path = BASE_DIR / "Storage" / "sesion_whatsapp"

    WHATSAPP_PORT: str = os.getenv("PUERTO_WHATSAPP", "9222")
    HEADLESS: bool = os.getenv("MODO_HEADLESS", "False").lower() == "true"
    RAM_LIMIT_MB: int = int(os.getenv("LIMITE_RAM_MB", "800"))

    API_PORT: int = int(os.getenv("PUERTO_API", "8000"))
    API_KEY: str = os.getenv("API_KEY_SECRETA", "CHANGE_ME")
    ALLOWED_IPS: list[str] = [
        ip.strip() for ip in os.getenv("ALLOWED_IPS", "127.0.0.1").split(",")
    ]
    ALERT_NUMBER: str = os.getenv("NUMERO_ALERTA", "")



AppConfig.LOG_DIR.mkdir(parents=True, exist_ok=True)
AppConfig.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
AppConfig.SESSION_DIR.mkdir(parents=True, exist_ok=True)