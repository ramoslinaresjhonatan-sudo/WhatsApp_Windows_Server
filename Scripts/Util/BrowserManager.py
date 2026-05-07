import os
import asyncio
import psutil
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger("BrowserManager")

class BrowserManager:

    def __init__(self, user_data_dir, port="9222", headless=False):
        self.user_data_dir = user_data_dir
        self.port = port
        self.headless = headless
        self._playwright = None
        self._browser = None

    async def launch_and_maintain(self, url="https://web.whatsapp.com"):
        try:
            self._playwright = await async_playwright().start()
            
            args = [
                f"--remote-debugging-port={self.port}",
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
                "--mute-audio",
                "--js-flags='--max-old-space-size=256'",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-sync",
                "--disable-translate",
                "--hide-scrollbars",
                "--metrics-recording-only",
                "--no-pings"
            ]

            logger.info(f"   Launching Edge (Optimized) on port {self.port}...")
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
            logger.info(f"   [OK] Browser active and monitoring.")

            try:
                for proc in psutil.process_iter(['name', 'cmdline']):
                    if 'msedge' in proc.info['name'].lower():
                        cmd = str(proc.info.get('cmdline') or "")
                        if f"--remote-debugging-port={self.port}" in cmd:
                            p = psutil.Process(proc.pid)
                            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            except: pass

            while True:
                if len(self._browser.pages) == 0:
                    logger.warning("   [!] All tabs closed. Stopping...")
                    break
                
                try:
                    for p in self._browser.pages:
                        if "whatsapp.com" in p.url:
                            btn = p.get_by_role("button", name="Usar aqui")
                            if await btn.is_visible(timeout=500):
                                logger.info("   [!] Claiming session from another window...")
                                await btn.click()
                except: pass

                await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"   [X] BrowserManager Error: {e}")
        finally:
            await self.stop()

    async def stop(self):
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            logger.info("   Browser Manager stopped.")
        except: pass
