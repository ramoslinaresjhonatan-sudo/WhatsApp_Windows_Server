import os
import time
import asyncio
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger("PictureMarco")

_BASE = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
STORAGE_DIR = os.path.join(_BASE, 'Storage', 'imagenes')

class picture:
    def __init__(self):
        os.makedirs(STORAGE_DIR, exist_ok=True)

    async def crear_imagen(self, html: str, nombre_base: str = "ticket"):
        """
        Renderiza HTML y devuelve la ruta de la imagen.
        """
        import time
        filename = f"{nombre_base}_{int(time.time())}.png"
        output_path = os.path.join(STORAGE_DIR, filename)
        
        logger.info(f"   [PictureMarco] Renderizando HTML a {filename}...")
        
        async with async_playwright() as p:
            # Usamos headless=True para que no abra ventanas físicas
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    viewport={"width": 800, "height": 600},
                    device_scale_factor=2
                )
                page = await context.new_page()
                
                # Cargamos el contenido
                await page.set_content(html)
                
                # Esperamos a que los recursos carguen
                await page.wait_for_load_state("networkidle", timeout=10000)
                
                # Capturamos el body
                element = page.locator("body")
                await element.screenshot(path=output_path)
                
                logger.info(f"   [PictureMarco] Imagen creada: {output_path}")
                return output_path
            except Exception as e:
                logger.error(f"   [PictureMarco] Error renderizando: {e}")
                raise e
            finally:
                await browser.close()