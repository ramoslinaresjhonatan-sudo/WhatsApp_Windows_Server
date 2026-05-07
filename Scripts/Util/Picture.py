import os
import time
from playwright.async_api import async_playwright

class Picture:
    def __init__(self):
        # Definir y crear la ruta de almacenamiento
        self.storage_dir = os.path.abspath(os.path.join(os.getcwd(), "storage", "imagenestemporales"))
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, exist_ok=True)

    async def crear_imagen(self, html_content, nombre_base="captura"):
        """
        Renderiza el contenido HTML y lo guarda como imagen PNG.
        Devuelve la ruta absoluta del archivo creado.
        """
        nombre_archivo = f"{nombre_base}_{int(time.time())}.png"
        ruta_completa = os.path.join(self.storage_dir, nombre_archivo)

        async with async_playwright() as p:
            # Iniciamos un navegador ligero en modo oculto
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Cargamos el HTML
            await page.set_content(html_content)
            
            # Esperamos a que cualquier recurso (como la imagen del src) cargue
            await page.wait_for_load_state("networkidle")
            
            # Tomamos la captura de pantalla ajustada al contenido
            await page.screenshot(path=ruta_completa, full_page=True)
            
            await browser.close()

        return ruta_completa

    def generar_html_imagen(self, ruta_o_url_imagen):
        """
        Genera el código HTML básico para una imagen.
        """
        html = f"""
        <html>
        <body style="margin:0; padding:0; display:inline-block;">
            <img src="{ruta_o_url_imagen}" style="display:block; max-width:100%;">
        </body>
        </html>
        """
        return html