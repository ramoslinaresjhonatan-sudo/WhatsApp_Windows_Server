from pathlib import Path
from playwright.sync_api import sync_playwright

_BASE_DIR = Path(__file__).resolve().parent.parent.parent

from dotenv import load_dotenv
load_dotenv(_BASE_DIR / ".env")

from Config.Setting import AppConfig


def login() -> None:
    print("Opening WhatsApp Web — please scan the QR code …")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(AppConfig.SESSION_DIR),
            headless=False,
            channel="msedge",
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://web.whatsapp.com")

        try:
            page.wait_for_selector('#pane-side', timeout=120_000)
            print("Login successful! Session saved.")
        except Exception:
            print("Timed out or window closed before login completed.")
        finally:
            context.close()


if __name__ == "__main__":
    login()