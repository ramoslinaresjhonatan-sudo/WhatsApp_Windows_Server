from playwright.sync_api import sync_playwright
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, '.env'))

def iniciar_sesion():
    user_data_dir = os.path.join(BASE_DIR, 'Storage', 'sesion_whatsapp')
    os.makedirs(os.path.dirname(user_data_dir), exist_ok=True)
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            channel="msedge",
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        print("Abriendo WhatsApp Web. Por favor, escanea el código QR...")
        page.goto("https://web.whatsapp.com")
        
        try:
            page.wait_for_selector('div[id="pane-side"]', timeout=60000)
            print("¡Inicio de sesión exitoso!")
        except Exception:
            print("Se acabó el tiempo o cerraste la ventana.")
            
        context.close()

if __name__ == "__main__":
    iniciar_sesion()