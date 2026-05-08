import os
import asyncio
import logging
import psutil
import subprocess
from pathlib import Path
from playwright.async_api import async_playwright, Error as PlaywrightError

from Config.Setting import AppConfig

from Scripts.Util.Logger import setup_logger

logger = setup_logger("WhatsApp", "whatsapp.log")

SEL_SIDEBAR       = "#side"
SEL_MAIN          = "#main"
SEL_LOADING       = 'div[data-testid="loading"]'
SEL_BTN_ATTACH    = 'span[data-icon="plus-rounded"], button[aria-label="Adjuntar"], span[data-icon="plus"], span[data-icon="clip"]'
SEL_BTN_SEND      = 'span[data-icon="wds-ic-send-filled"], span[data-icon="send"], [aria-label="Enviar"], button:has(span[data-icon="send"])'
SEL_MSG_PENDING   = 'span[data-icon="msg-time"]'

SEL_SEARCH = [
    'input[role="textbox"][aria-label*="Busc"]',
    'input[placeholder*="Busc"]',
    'input[aria-label*="Busc"]',
    '#side div[contenteditable="true"]',
    'div[contenteditable="true"][data-tab="3"]',
    'div[data-testid="chat-list-search"]',
    'div[role="textbox"][aria-placeholder*="Busc"]',
    'div[role="textbox"][aria-label*="Busc"]',
]

SEL_TEXT_INPUT = [
    'div.lexical-rich-text-input div[contenteditable="true"]',
    'div[data-testid="conversation-compose-box-input"]',
    'div[role="textbox"][contenteditable="true"]',
    '#main footer div[contenteditable="true"]',
    'footer div[role="textbox"]',
    'p.selectable-text.copyable-text',
    'div[contenteditable="true"]',
]

SEL_CAPTION = [
    'div.lexical-rich-text-input div[contenteditable="true"]',
    'div[contenteditable="true"][role="textbox"]',
    'div[data-tab="10"]',
    'div[data-tab="6"]',
]

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


class MacroWhatsApp:

    MAX_RETRIES = 3
    RETRY_DELAY = 2.0

    def __init__(self):
        self.port       = AppConfig.WHATSAPP_PORT
        self.headless   = AppConfig.HEADLESS
        self.ram_limit  = AppConfig.RAM_LIMIT_MB
        self._playwright  = None
        self._browser     = None
        self._context     = None
        self._page        = None
        self._active_tasks = 0

    async def connect(self) -> bool:
        if self._page and not self._page.is_closed():
            return True
        try:
            if not self._playwright:
                self._playwright = await async_playwright().start()

            self._browser = await self._playwright.chromium.connect_over_cdp(
                f"http://localhost:{self.port}"
            )
            if not self._browser.contexts:
                logger.error("No browser contexts found. Is VentaDeWhatsapp running?")
                return False

            self._context = self._browser.contexts[0]

            self._page = next(
                (p for p in self._context.pages if "whatsapp.com" in p.url),
                self._context.pages[0] if self._context.pages else await self._context.new_page(),
            )

            await self._page.bring_to_front()
            return await self._validate_whatsapp()

        except PlaywrightError as exc:
            logger.error("CDP connection failed: %s", exc)
            await self._reset_connection()
            return False

    async def _validate_whatsapp(self) -> bool:
        try:
            await self._page.wait_for_selector(SEL_SIDEBAR, timeout=5_000)
            return True
        except PlaywrightError:
            return await self._open_whatsapp()

    async def _open_whatsapp(self) -> bool:
        try:
            if "whatsapp.com" not in self._page.url:
                await self._page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
            await self._page.wait_for_selector(SEL_SIDEBAR, timeout=60_000)
            return True
        except PlaywrightError as exc:
            logger.error("Could not load WhatsApp Web: %s", exc)
            return False

    async def _reset_connection(self) -> None:
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as exc:
                logger.debug("Error stopping playwright during reset: %s", exc)
        self._page = self._browser = self._playwright = None

    async def send(self, chat: str, message: str = None, files: list = None) -> bool:
        self._active_tasks += 1
        try:
            for attempt in range(1, self.MAX_RETRIES + 1):
                logger.info("Attempt %d/%d — sending to '%s' ...", attempt, self.MAX_RETRIES, chat)
                try:
                    if not await self.connect():
                        raise ConnectionError("Could not connect to the browser.")

                    if not await self._navigate_to_chat(chat):
                        logger.error("Recipient '%s' not found or could not be verified.", chat)
                        return False

                    if message:
                        if not await self._send_text(message):
                            return False

                    if files:
                        if not await self._dispatch_files(files):
                            return False

                    if await self._confirm_sent():
                        logger.info("[OK] Message delivered to '%s'.", chat)
                        return True

                    logger.warning("Delivery not confirmed (attempt %d).", attempt)

                except (ConnectionError, PlaywrightError) as exc:
                    logger.error("Error on attempt %d: %s", attempt, exc)
                    await self._reset_connection()

                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_DELAY)

            logger.error("Failed to send to '%s' after %d attempts.", chat, self.MAX_RETRIES)
            return False
        finally:
            self._active_tasks -= 1

    async def message(self, chat: str, text: str) -> bool:
        return await self.send(chat, message=text)

    async def file(self, chat: str, path: str, text: str = "") -> bool:
        return await self.send(chat, message=text or None, files=[path])

    async def multiple(self, chat: str, paths: list, text: str = "") -> bool:
        return await self.send(chat, message=text or None, files=paths)

    async def check_and_clean_ram(self) -> None:
        try:
            api_ram = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
            total_ram = api_ram

            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                name = (proc.info.get("name") or "").lower()
                cmdline = str(proc.info.get("cmdline") or "")
                if "msedge" not in name or f"--remote-debugging-port={self.port}" not in cmdline:
                    continue
                try:
                    p = psutil.Process(proc.info["pid"])
                    total_ram += p.memory_info().rss / (1024 * 1024)
                    for child in p.children(recursive=True):
                        total_ram += child.memory_info().rss / (1024 * 1024)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if total_ram > self.ram_limit and self._active_tasks == 0:
                logger.info(
                    "RAM threshold exceeded (%.0f MB > %d MB). Resetting connection ...",
                    total_ram, self.ram_limit,
                )
                await self._reset_connection()

        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            logger.warning("RAM monitor error: %s", exc)

    async def _navigate_to_chat(self, name: str) -> bool:
        page = self._page

        try:
            await page.wait_for_selector(SEL_SIDEBAR, timeout=30_000)
            await page.wait_for_selector(SEL_LOADING, state="hidden", timeout=10_000)
        except PlaywrightError as exc:
            logger.debug("Sidebar wait timed out (continuing): %s", exc)

        try:
            await page.click(SEL_SIDEBAR, timeout=2_000)
        except PlaywrightError:
            pass

        search_box = await self._find_search_box(page)

        if search_box:
            try:
                await search_box.click(force=True)
            except PlaywrightError:
                pass

        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await page.keyboard.type(name, delay=80)

        await self._wait_for_search_results(page, name)

        await self._click_contact(page, name)

        await asyncio.sleep(0.8)
        return await self._wait_for_chat_header(name)

    async def _find_search_box(self, page):
        for sel in SEL_SEARCH:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=800):
                    return el
            except PlaywrightError:
                continue

        for shortcut in ["Control+Alt+/", "Alt+K", "Control+f", "/"]:
            try:
                await page.keyboard.press("Escape")
                await page.keyboard.press(shortcut)
                await asyncio.sleep(0.4)
                for sel in SEL_SEARCH:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=400):
                        return el
            except PlaywrightError:
                continue
        return None

    async def _wait_for_search_results(self, page, name: str) -> None:
        result_sel = f'div[data-testid="list-item"]:has-text("{name}")'
        try:
            await page.wait_for_selector(result_sel, timeout=5_000)
        except PlaywrightError:
            await asyncio.sleep(1.0)

    async def _click_contact(self, page, name: str) -> None:
        selectors = [
            f'span[title="{name}"]',
            f'div[data-testid="list-item"] span[title*="{name}" i]',
            f'div[data-testid="list-item"]:has-text("{name}")',
            f'div[role="listitem"]:has-text("{name}")',
        ]
        for sel in selectors:
            try:
                contact = page.locator(sel).first
                if await contact.is_visible(timeout=1_000):
                    await contact.click()
                    logger.info("Clicked contact using selector: %s", sel)
                    return
            except PlaywrightError:
                continue
        logger.warning("Could not find contact '%s' with any selector.", name)

    async def _wait_for_chat_header(self, name: str) -> bool:
        try:
            header = self._page.locator(f"{SEL_MAIN} header")
            await header.wait_for(timeout=15_000)
            
            ignore_list = {"detalles del perfil", "click para info", "escribiendo...", "en línea", "online"}
            
            text = ""
            for _ in range(15):
                try:
                    target = header.locator(f'text="{name}"').first
                    if await target.is_visible(timeout=300):
                        text = await target.text_content()
                        if text: break
                except PlaywrightError:
                    pass

                elements = header.locator('span, div[role="button"]')
                count = await elements.count()
                for i in range(count):
                    el = elements.nth(i)
                    if await el.is_visible(timeout=100):
                        val = await el.text_content()
                        if val and val.strip() and val.strip().lower() not in ignore_list:
                            if name.lower() in val.lower():
                                text = val.strip()
                                break
                if text: break
                await asyncio.sleep(0.5)
            
            logger.info("Chat validation: Expected '%s', Detected '%s'", name, text)
            
            if not text:
                logger.error("No contact name detected in header. Aborting to prevent wrong delivery.")
                return False
                
            return name.lower() in text.lower()
        except PlaywrightError as exc:
            logger.debug("Chat header validation failed: %s", exc)
            return False

    async def _get_text_input(self):
        for sel in SEL_TEXT_INPUT:
            try:
                el = self._page.locator(sel).first
                await el.wait_for(state="visible", timeout=2_000)
                return el
            except PlaywrightError:
                continue
        return self._page.locator('div[contenteditable="true"]').last

    async def _send_text(self, text: str) -> bool:
        box = await self._get_text_input()
        if not box:
            return False
        await box.click()
        await box.fill("")
        await self._page.keyboard.insert_text(text)
        await asyncio.sleep(0.3)
        await self._page.keyboard.press("Enter")
        await asyncio.sleep(0.5)
        return True

    async def _dispatch_files(self, files: list) -> bool:
        valid = [Path(f).resolve() for f in files if Path(f).exists()]
        if not valid:
            logger.error("No valid file paths provided: %s", files)
            return False

        is_image = any(p.suffix.lower() in IMAGE_EXTENSIONS for p in valid)
        str_paths = [str(p) for p in valid]

        if is_image:
            logger.info("Image detected — using multimedia channel.")
            return await self._send_multimedia(str_paths)
        else:
            logger.info("Document detected — using file channel.")
            return await self._send_files(str_paths)

    async def _send_files(self, paths: list, caption: str = None) -> bool:
        page = self._page

        if not self.headless:
            try:
                logger.info("Attaching %d file(s) via clipboard (visible mode) ...", len(paths))
                await self._paste_via_clipboard(paths, page)
                if not await self._wait_for_attachment_preview(page):
                    return False
                if caption:
                    await self._write_caption(caption, page)
                await self._click_send()
                return True
            except Exception as exc:
                logger.warning("Clipboard attach failed: %s. Falling back to file-chooser ...", exc)

        try:
            logger.info("[Headless] Using file-chooser interceptor ...")
            async with page.expect_file_chooser(timeout=10_000) as fc_info:
                try:
                    await page.locator(SEL_BTN_ATTACH).first.click(timeout=3_000)
                    await asyncio.sleep(0.4)
                    doc_btn = page.locator(
                        'span[data-icon="attach-document"], [aria-label="Documento"]'
                    ).first
                    await doc_btn.click(timeout=2_000)
                except PlaywrightError as exc:
                    logger.warning("Could not open attach menu: %s", exc)
                    await page.locator('input[type="file"]').first.click()

            fc = await fc_info.value
            await fc.set_files(paths)
            if not await self._wait_for_attachment_preview(page):
                return False
            if caption:
                await self._write_caption(caption, page)
            await self._click_send()
            return True

        except PlaywrightError as exc:
            logger.error("Critical error during file attach: %s", exc)
            try:
                await page.keyboard.press("Escape")
            except PlaywrightError:
                pass
            return False

    async def _send_multimedia(self, paths: list, caption: str = None) -> bool:
        page = self._page
        valid = [str(Path(p).resolve()) for p in paths if Path(p).exists()]
        if not valid:
            return False

        if not self.headless:
            try:
                logger.info("Pasting %d image(s) via clipboard ...", len(valid))
                await self._paste_via_clipboard(valid, page)
                if not await self._wait_for_attachment_preview(page):
                    return False
                if caption:
                    await self._write_caption(caption, page)
                    await asyncio.sleep(0.3)
                await self._click_send()
                return True
            except Exception as exc:
                logger.warning("Multimedia paste failed: %s. Falling back to selector ...", exc)

        logger.info("Using 'Photos & Videos' selector ...")
        try:
            btn_attach = page.locator(SEL_BTN_ATTACH).first
            await btn_attach.wait_for(state="visible", timeout=5_000)
            await btn_attach.click(force=True)
            await asyncio.sleep(0.6)
        except PlaywrightError as exc:
            logger.error("Could not open attach menu: %s", exc)
            return False

        try:
            photo_selectors = [
                'span[data-icon="attach-image"]',
                '[aria-label="Fotos y videos"]',
                '[aria-label="Photos & Videos"]',
                'li:has(span[data-icon="attach-image"])',
                'button:has(span[data-icon="attach-image"])',
            ]
            async with page.expect_file_chooser(timeout=10_000) as fc_info:
                btn_photos = None
                for sel in photo_selectors:
                    try:
                        el = page.locator(sel).first
                        if await el.is_visible(timeout=400):
                            btn_photos = el
                            break
                    except PlaywrightError:
                        continue

                if not btn_photos:
                    btn_photos = page.get_by_role("button").filter(has_text="Fotos y videos")
                await btn_photos.click(force=True)

            fc = await fc_info.value
            await fc.set_files(valid)

        except PlaywrightError as exc:
            logger.error("File-chooser error: %s", exc)
            try:
                await page.keyboard.press("Escape")
            except PlaywrightError:
                pass
            return False

        if not await self._wait_for_attachment_preview(page):
            return False
        if caption:
            await self._write_caption(caption, page)
            await asyncio.sleep(0.3)
        await self._click_send()
        return True

    async def _wait_for_attachment_preview(self, page) -> bool:
        preview_selectors = [
            'div[data-testid="media-caption-input-container"]',
            'div[data-testid="send-image-popup"]',
            'div[class*="popup-contents"]',
        ]
        for sel in preview_selectors:
            try:
                await page.wait_for_selector(sel, timeout=6_000)
                return True
            except PlaywrightError:
                continue
        logger.warning("Attachment preview did not appear within timeout.")
        return False

    async def _paste_via_clipboard(self, paths: list, page) -> None:
        escaped = " ".join(f"$f.Add('{p.replace(chr(39), chr(39)*2)}');" for p in paths)
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "[System.Windows.Forms.Clipboard]::Clear(); "
            "$f = New-Object System.Collections.Specialized.StringCollection; "
            + escaped
            + "[System.Windows.Forms.Clipboard]::SetFileDropList($f)"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True,
            creationflags=0x08000000, timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Clipboard script failed: {result.stderr.strip()}")

        await asyncio.sleep(0.4)
        input_box = await self._get_text_input()
        await input_box.click()
        await page.keyboard.press("Control+V")

    async def _write_caption(self, text: str, page) -> None:
        for sel in SEL_CAPTION:
            try:
                cap = page.locator(sel).last
                if await cap.is_visible(timeout=2_000):
                    await cap.click()
                    await page.keyboard.insert_text(text)
                    await asyncio.sleep(0.3)
                    return
            except PlaywrightError:
                continue

    async def _click_send(self) -> None:
        send_selectors = [
            'div[role="button"] span[data-icon="send"]',
            'div[role="button"] span[data-icon="wds-ic-send-filled"]',
            'div[data-testid="send"]',
            'button:has(span[data-icon="send"])',
            '[aria-label="Enviar"]',
            '[aria-label="Send"]',
            'span[data-icon="send"]',
        ]
        for sel in send_selectors:
            try:
                btn = self._page.locator(sel).last
                if await btn.is_visible(timeout=2_000):
                    await btn.click(force=True)
                    return
            except PlaywrightError:
                continue
        await self._page.keyboard.press("Enter")

    async def _confirm_sent(self) -> bool:
        await asyncio.sleep(1.0)
        try:
            await self._page.locator(SEL_MSG_PENDING).last.wait_for(
                state="hidden", timeout=15_000
            )
            return True
        except PlaywrightError:
            logger.warning("Message status timeout — clock icon still visible.")
            return False


    async def close(self) -> None:
        await self._reset_connection()

    async def _is_page_active(self) -> bool:
        try:
            return bool(self._page and not self._page.is_closed())
        except PlaywrightError:
            return False
