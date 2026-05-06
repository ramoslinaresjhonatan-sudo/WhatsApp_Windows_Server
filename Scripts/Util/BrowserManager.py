import os
import time
import psutil
import ctypes
import logging
from playwright.sync_api import sync_playwright

logger = logging.getLogger("BrowserManager")

class BrowserManager:

    def __init__(self, user_data_dir, puerto="9222", headless=False):
        self.user_data_dir = user_data_dir
        self.puerto = puerto
        self.headless = headless

    def lanzar_y_mantener(self, urls=["https://web.whatsapp.com"]):
        if isinstance(urls, str):
            urls = [urls]

        with sync_playwright() as p:
            try:
                logger.info(f"Lanzando navegador en puerto {self.puerto}...")
                context = p.chromium.launch_persistent_context(
                    user_data_dir=self.user_data_dir,
                    channel="msedge",
                    headless=self.headless,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
                    no_viewport=True,
                    args=[
                        f"--remote-debugging-port={self.puerto}",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-infobars",
                        "--start-maximized",
                        "--mute-audio",
                        "--disable-dev-shm-usage",
                        "--disable-extensions",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-background-networking",
                        "--disable-sync",
                        "--disable-component-update",
                        "--disable-default-apps",
                        "--disable-notifications",
                        "--disable-offer-store-unmasked-wallet-cards",
                        "--disable-popup-blocking",
                        "--disable-print-preview",
                        "--disable-speech-api",
                        "--password-store=basic"
                    ],
                    ignore_default_args=["--enable-automation"]
                )
                
                # El bloqueo de imágenes se moverá a MacroWhatsApp.py para que sea dinámico
                
                # Abrir cada URL en una pestaña nueva
                for i, url in enumerate(urls):
                    if i == 0 and context.pages:
                        page = context.pages[0]
                    else:
                        page = context.new_page()
                    
                    logger.info(f"Abriendo pestaña {i+1}: {url}")
                    
                    page.goto(url, wait_until="domcontentloaded")
                
                logger.info("Monitoreando estado del navegador (Control de Popups)...")
                while True:
                    # Control de popups de sesión y limpieza de duplicados
                    try:
                        all_pages = context.pages
                        whatsapp_pages = [p for p in all_pages if "whatsapp.com" in p.url]
                        
                        # Si hay más de una pestaña de WhatsApp abierta, cerramos las extras para evitar conflictos
                        if len(whatsapp_pages) > 1:
                            for extra_page in whatsapp_pages[1:]:
                                try: extra_page.close()
                                except: pass
                        
                        # En la pestaña principal de WhatsApp, buscamos el botón de "Usar aquí"
                        if whatsapp_pages:
                            p = whatsapp_pages[0]
                            usar_aqui = p.get_by_role("button", name="Usar aquí")
                            if usar_aqui.is_visible(timeout=500):
                                logger.warning("⚠️ Sesión detectada en otra ventana. Reclamando sesión...")
                                usar_aqui.click()
                                logger.info("✅ Sesión reclamada con éxito.")
                                time.sleep(5) # Esperamos a que la sesión se estabilice
                    except Exception:
                        pass # Si una pestaña se cierra durante el proceso, ignoramos
                            
                    time.sleep(5) 
                    
            except Exception as e:
                logger.error(f"Error en el ciclo del navegador: {e}")
            finally:
                logger.info("Cerrando manager de navegador...")
