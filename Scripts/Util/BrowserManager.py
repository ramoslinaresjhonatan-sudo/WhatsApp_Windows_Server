import os
import asyncio
import psutil
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger("BrowserManager")

class BrowserManager:

    def __init__(self, user_data_dir, puerto="9222", headless=False):
        self.user_data_dir = user_data_dir
        self.puerto = puerto
        self.headless = headless
        self._playwright = None
        self._browser = None

    async def lanzar_y_mantener(self, url="https://web.whatsapp.com"):
        """Lanza el navegador y mantiene la sesión activa en modo asíncrono."""
        try:
            self._playwright = await async_playwright().start()
            
            args = [
                f"--remote-debugging-port={self.puerto}",
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check"
            ]

            logger.info(f"   Lanzando Edge en puerto {self.puerto}...")
            self._browser = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                channel="msedge",
                headless=self.headless,
                args=args,
                no_viewport=True,
                ignore_https_errors=True
            )

            if not self._browser.pages:
                page = await self._browser.new_page()
            else:
                page = self._browser.pages[0]

            await page.goto(url)
            logger.info(f"   [✓] Navegador activo y monitoreando.")

            # Bucle de monitoreo para mantener el proceso vivo
            while True:
                if len(self._browser.pages) == 0:
                    logger.warning("   [!] Todas las pestañas cerradas. Deteniendo...")
                    break
                
                # Manejo de popups de sesión ("Usar aquí")
                try:
                    for p in self._browser.pages:
                        if "whatsapp.com" in p.url:
                            btn = p.get_by_role("button", name="Usar aquí")
                            if await btn.is_visible(timeout=500):
                                logger.info("   [!] Reclamando sesión de otra ventana...")
                                await btn.click()
                except: pass

                await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"   [✗] Error en BrowserManager: {e}")
        finally:
            await self.detener()

    async def detener(self):
        """Cierra el navegador de forma segura."""
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            logger.info("   Manager de navegador detenido.")
        except: pass
