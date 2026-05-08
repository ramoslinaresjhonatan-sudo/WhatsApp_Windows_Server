import asyncio
import logging
import psutil
from playwright.async_api import async_playwright, BrowserContext, Error as PlaywrightError

from Config.Setting import AppConfig

logger = logging.getLogger("BrowserManager")

_BROWSER_ARGS: list[str] = [
    f"--remote-debugging-port={AppConfig.WHATSAPP_PORT}",
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
    "--js-flags=--max-old-space-size=256",
    "--disable-background-networking",
    "--disable-default-apps",
    "--disable-sync",
    "--disable-translate",
    "--hide-scrollbars",
    "--metrics-recording-only",
    "--no-pings",
]

_WATCHDOG_INTERVAL = 5


class BrowserManager:

    def __init__(self):
        self._playwright = None
        self._browser: BrowserContext | None = None

    async def launch_and_maintain(self, url: str = "https://web.whatsapp.com") -> None:
        try:
            await self._launch(url)
            await self._watchdog()
        except PlaywrightError as exc:
            logger.error("Playwright error in BrowserManager: %s", exc)
        except Exception as exc:
            logger.exception("Unexpected error in BrowserManager: %s", exc)
        finally:
            await self._stop()

    async def _launch(self, url: str) -> None:
        self._playwright = await async_playwright().start()

        logger.info("Launching Edge (optimised) on port %s ...", AppConfig.WHATSAPP_PORT)
        self._browser = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(AppConfig.SESSION_DIR),
            channel="msedge",
            headless=AppConfig.HEADLESS,
            args=_BROWSER_ARGS,
            no_viewport=True,
            ignore_https_errors=True,
        )

        page = self._browser.pages[0] if self._browser.pages else await self._browser.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        logger.info("[OK] Browser active and monitoring.")

        self._lower_browser_priority()

    def _lower_browser_priority(self) -> None:
        try:
            for proc in psutil.process_iter(["name", "cmdline"]):
                name = (proc.info.get("name") or "").lower()
                cmdline = str(proc.info.get("cmdline") or "")
                if "msedge" in name and f"--remote-debugging-port={AppConfig.WHATSAPP_PORT}" in cmdline:
                    psutil.Process(proc.pid).nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError) as exc:
            logger.warning("Could not lower browser priority: %s", exc)

    async def _watchdog(self) -> None:
        assert self._browser is not None
        while True:
            if not self._browser.pages:
                logger.warning("All browser tabs closed — stopping watchdog.")
                break

            await self._reclaim_session()
            await asyncio.sleep(_WATCHDOG_INTERVAL)

    async def _reclaim_session(self) -> None:
        assert self._browser is not None
        for page in self._browser.pages:
            if "whatsapp.com" not in page.url:
                continue
            try:
                for btn_name in ["Usar aqui", "Use here", "Usar aquí"]:
                    btn = page.get_by_role("button", name=btn_name)
                    if await btn.is_visible(timeout=300):
                        logger.info("Reclaiming session from another window (%s) ...", btn_name)
                        await btn.click()
                        break
            except PlaywrightError:
                pass

    async def _stop(self) -> None:
        try:
            if self._browser:
                await self._browser.close()
        except PlaywrightError as exc:
            logger.warning("Error closing browser: %s", exc)
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception as exc:
            logger.warning("Error stopping Playwright: %s", exc)
        logger.info("BrowserManager stopped.")
