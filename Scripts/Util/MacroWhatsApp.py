import os
import asyncio
import logging
import psutil
import ctypes
import subprocess
from playwright.async_api import async_playwright
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, '.env'))

logger = logging.getLogger("WhatsApp")

SEL_SIDEBAR       = '#side'
SEL_MAIN          = '#main'
SEL_LOADING       = 'div[data-testid="loading"]'
SEL_BTN_ADJUNTAR  = 'span[data-icon="plus-rounded"], button[aria-label="Adjuntar"], span[data-icon="plus"], span[data-icon="clip"]'
SEL_FILE_INPUT    = 'input[type="file"]'
SEL_BTN_ENVIAR    = 'span[data-icon="wds-ic-send-filled"], span[data-icon="send"], [aria-label="Enviar"], button:has(span[data-icon="send"])'
SEL_MSG_PENDIENTE = 'span[data-icon="msg-time"]'
SEL_MSG_ENVIADO   = 'span[data-icon="msg-dblcheck"], span[data-icon="msg-check"]'
SEL_SEARCH        = [
    'input[role="textbox"][aria-label*="Busc"]',
    'input[placeholder*="Busc"]',
    'input[aria-label*="Busc"]',
    '#side div[contenteditable="true"]',
    'div[contenteditable="true"][data-tab="3"]',
    'div[data-testid="chat-list-search"]',
    'div[role="textbox"][aria-placeholder*="Busc"]',
    'div[role="textbox"][aria-label*="Busc"]',
]
SEL_INPUT_TEXTO   = [
    'div.lexical-rich-text-input div[contenteditable="true"]',
    'div[contenteditable="true"][role="textbox"]',
    'div[data-testid="conversation-compose-box-input"]',
    'div[contenteditable="true"][data-tab="10"]',
    '#main footer div[contenteditable="true"]',
    'div[title="Escribe un mensaje"]',
    'div[title="Type a message"]',
    'footer div[role="textbox"]',
]
SEL_CAPTION = [
    'div.lexical-rich-text-input div[contenteditable="true"]',
    'div[contenteditable="true"][role="textbox"]',
    'div[data-tab="10"]',
    'div[data-tab="6"]',
]

class MacroWhatsApp:

    MAX_RETRIES = 3
    RETRY_DELAY = 2.0

    def __init__(self):
        self.port      = os.getenv("PUERTO_WHATSAPP", "9222")
        self.headless  = os.getenv("MODO_HEADLESS", "False").lower() == "true"
        self.ram_limit = int(os.getenv("LIMITE_RAM_MB", "1024"))
        self._playwright   = None
        self._browser      = None
        self._context      = None
        self._page         = None
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
                logger.error("No contexts found in browser. Is VentaDeWhatsapp running?")
                return False

            self._context = self._browser.contexts[0]

            self._page = None
            for p in self._context.pages:
                if "whatsapp.com" in p.url:
                    self._page = p
                    break

            if not self._page:
                self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

            await self._page.bring_to_front()
            return await self._validate_whatsapp()

        except Exception as e:
            logger.error(f"Error connecting to browser: {e}")
            await self._clean_connection()
            return False

    async def _validate_whatsapp(self) -> bool:
        try:
            await self._page.wait_for_selector(SEL_SIDEBAR, timeout=5000)
            return True
        except:
            return await self._open_whatsapp()

    async def _open_whatsapp(self) -> bool:
        try:
            if "whatsapp.com" not in self._page.url:
                await self._page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
            await self._page.wait_for_selector(SEL_SIDEBAR, timeout=60000)
            return True
        except Exception as e:
            logger.error(f"Could not load WhatsApp Web: {e}")
            return False

    async def _clean_connection(self):
        try:
            if self._playwright:
                await self._playwright.stop()
        except: pass
        finally:
            self._page      = None
            self._browser   = None
            self._playwright = None

    async def send(self, chat: str, message: str = None, files: list = None) -> bool:
        self._active_tasks += 1
        attempt = 0

        while attempt < self.MAX_RETRIES:
            attempt += 1
            logger.info(f"Attempt {attempt}/{self.MAX_RETRIES} - Sending to '{chat}'...")

            try:
                if not await self.connect():
                    raise ConnectionError("Could not connect to browser.")

                await self._search_chat(chat)

                if message:
                    await self._send_text(message)
                    await asyncio.sleep(1.5)

                if files:
                    logger.info(f"   [Send] Processing attachments: {files}")
                    img_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
                    is_image = any(str(f).lower().strip().endswith(img_extensions) for f in files)
                    
                    if is_image:
                        logger.info("   [Send] Image detected. Using multimedia channel.")
                        await self._send_multimedia(files, caption=None)
                    else:
                        logger.info("   [Send] Document detected. Using file channel.")
                        await self._send_files(files)

                if await self._verify_send():
                    logger.info(f"   [OK] Confirmed: message sent to '{chat}'.")
                    return True
                else:
                    logger.warning(f"   [!] Could not confirm send (attempt {attempt}).")

            except Exception as e:
                logger.error(f"   Error in attempt {attempt}: {e}")
                await self._clean_connection()

            if attempt < self.MAX_RETRIES:
                await asyncio.sleep(self.RETRY_DELAY)

        logger.error(f"Failed to send to '{chat}' after {self.MAX_RETRIES} attempts.")
        self._active_tasks -= 1
        return False

    async def check_and_clean_ram(self):
        try:
            api_proc = psutil.Process(os.getpid())
            total_ram = api_proc.memory_info().rss / (1024 * 1024)
            
            edge_pids = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if 'msedge' in proc.info['name'].lower():
                    cmd = str(proc.info.get('cmdline') or "")
                    if f"--remote-debugging-port={self.port}" in cmd:
                        edge_pids.append(proc.info['pid'])
            
            for pid in edge_pids:
                try:
                    p = psutil.Process(pid)
                    total_ram += p.memory_info().rss / (1024 * 1024)
                    for child in p.children(recursive=True):
                        total_ram += child.memory_info().rss / (1024 * 1024)
                except: continue

            if total_ram > self.ram_limit:
                logger.info(f"RAM cleanup needed ({total_ram:.0f}MB > {self.ram_limit}MB). Restarting browser...")
                await self._clean_connection()
        except Exception as e:
            pass

    async def message(self, chat: str, text: str) -> bool:
        return await self.send(chat, message=text)

    async def file(self, chat: str, path: str, text: str = "") -> bool:
        return await self.send(chat, message=text or None, files=[path])

    async def multiple(self, chat: str, paths: list, text: str = "") -> bool:
        return await self.send(chat, message=text or None, files=paths)

    async def _search_chat(self, name: str):
        page = self._page

        try:
            await page.wait_for_selector(SEL_SIDEBAR, timeout=30000)
            await page.wait_for_selector(SEL_LOADING, state="hidden", timeout=10000)
        except: pass

        try: await page.click(SEL_SIDEBAR, timeout=2000)
        except: pass

        search_box = None
        for sel in SEL_SEARCH:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1000):
                    search_box = el
                    break
            except: continue

        if not search_box:
            for shortcut in ["Control+Alt+/", "Alt+K", "Control+f", "/"]:
                try:
                    await page.keyboard.press("Escape")
                    await page.keyboard.press(shortcut)
                    await asyncio.sleep(0.5)
                    for sel in SEL_SEARCH:
                        el = page.locator(sel).first
                        if await el.is_visible(timeout=500):
                            search_box = el
                            break
                    if search_box: break
                except: pass

        if search_box:
            try: await search_box.click(force=True)
            except: pass

        await asyncio.sleep(0.3)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await asyncio.sleep(0.2)
        await page.keyboard.type(name, delay=80)
        await asyncio.sleep(2.5) 

        selectors = [
            f'span[title="{name}"]',
            f'div[data-testid="list-item"] span[title="{name}"]',
            f'div[role="listitem"] span[title="{name}"]'
        ]
        
        found = False
        for sel in selectors:
            try:
                contact = page.locator(sel).first
                if await contact.is_visible(timeout=1000):
                    await contact.click()
                    found = True
                    break
            except: continue

        if not found:
            logger.warning(f"   [!] Could not click on '{name}', forcing with Enter...")
            await page.keyboard.press("Enter")

        await asyncio.sleep(1.5)
        return await self._wait_for_chat_to_open(name)

    async def _wait_for_chat_to_open(self, name: str) -> bool:
        try:
            header = self._page.locator(f"{SEL_MAIN} header")
            await header.wait_for(timeout=10000)
            title = header.locator('span[dir="auto"]').first
            await title.wait_for(state="visible", timeout=5000)
            text = await title.text_content()
            if text and name.lower() in text.lower():
                return True
            return False
        except:
            return False

    async def _get_text_input(self):
        for sel in SEL_INPUT_TEXTO:
            try:
                el = self._page.locator(sel).first
                await el.wait_for(state="visible", timeout=2000)
                return el
            except: continue
        return self._page.locator('div[contenteditable="true"]').last

    async def _send_text(self, text: str):
        box = await self._get_text_input()
        await box.click()
        await box.fill("")
        await asyncio.sleep(0.2)
        await self._page.keyboard.insert_text(text)
        await asyncio.sleep(0.3)
        await self._page.keyboard.press("Enter")

    async def _send_files(self, paths: list, caption: str = None):
        valid_paths = [os.path.abspath(p) for p in paths if os.path.exists(p)]
        if not valid_paths:
            logger.error("   [X] No valid files to attach.")
            return

        page = self._page
        
        if not self.headless:
            try:
                logger.info(f"   Attaching {len(valid_paths)} file(s) via clipboard (Visible Mode)...")
                await self._paste_files_from_clipboard(valid_paths, page)
                await asyncio.sleep(4)
                if caption: await self._write_caption(caption, page)
                await self._click_send()
                return
            except Exception as e:
                logger.warning(f"   [!] Clipboard failed: {e}. Trying input method...")

        try:
            logger.info(f"   [HEADLESS MODE] Using File Chooser interceptor...")
            
            async with page.expect_file_chooser() as fc_info:
                try:
                    await page.locator(SEL_BTN_ADJUNTAR).first.click(timeout=3000)
                    await asyncio.sleep(0.5)
                    
                    doc_btn = page.locator('span[data-icon="attach-document"], [aria-label="Documento"]').first
                    await doc_btn.click(timeout=2000)
                except Exception as e:
                    logger.warning(f"      [!] Could not trigger menu: {e}")
                    await page.locator('input[type="file"]').first.click()

            file_chooser = await fc_info.value
            await file_chooser.set_files(valid_paths)
            
            await asyncio.sleep(7) 
            
            if caption:
                await self._write_caption(caption, page)

            await self._click_send()

        except Exception as e:
            logger.error(f"   [X] Critical error attaching: {e}")
            try: await page.keyboard.press("Escape")
            except: pass

    async def _paste_files_from_clipboard(self, paths: list, page):
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "[System.Windows.Forms.Clipboard]::Clear(); "
            "$f = New-Object System.Collections.Specialized.StringCollection; "
            + " ".join(f"$f.Add('{p.replace(chr(39), chr(39)*2)}');" for p in paths)
            + "[System.Windows.Forms.Clipboard]::SetFileDropList($f)"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            creationflags=0x08000000, timeout=10
        )
        await asyncio.sleep(0.5)
        input_box = await self._get_text_input()
        await input_box.click()
        await page.keyboard.press("Control+V")
        await asyncio.sleep(3.5)

    async def _write_caption(self, text: str, page):
        for sel in SEL_CAPTION:
            try:
                cap = page.locator(sel).last
                if await cap.is_visible(timeout=2000):
                    await cap.click()
                    await page.keyboard.insert_text(text)
                    await asyncio.sleep(0.4)
                    return
            except: continue

    async def _click_send(self):
        try:
            selectors = [
                'div[role="button"] span[data-icon="send"]',
                'div[role="button"] span[data-icon="wds-ic-send-filled"]',
                'div[data-testid="send"]',
                'button:has(span[data-icon="send"])',
                '[aria-label="Enviar"]',
                '[aria-label="Send"]',
                'span[data-icon="send"]'
            ]

            btn_found = False
            for sel in selectors:
                try:
                    btn = self._page.locator(sel).last
                    if await btn.is_visible(timeout=2000):
                        await btn.click(force=True)
                        btn_found = True
                        break
                except: continue

            if not btn_found:
                await self._page.keyboard.press("Enter")
            
        except Exception as e:
            await self._page.keyboard.press("Enter")

    async def send_capture(self, chat: str, html: str, caption: str = None) -> bool:
        from Scripts.Util.PictureMarco import picture as EngineClass
        from Scripts.Util.Storage import Storage
        
        p = EngineClass()
        s = Storage("imagenes")
        
        try:
            if not await self.connect():
                return False
            
            if not await self._search_chat(chat):
                return False

            img_path = await p.create_image(html)
            success = await self._send_multimedia([img_path], caption)
            
            if success:
                s.delete_file(img_path)
            
            return success
        except Exception as e:
            return False

    async def _verify_send(self) -> bool:
        await asyncio.sleep(1.5)
        try:
            await self._page.locator(SEL_MSG_PENDIENTE).last.wait_for(
                state="hidden", timeout=15000
            )
            return True
        except:
            return True

    async def _send_multimedia(self, paths: list, caption: str = None) -> bool:
        page = self._page
        valid_paths = [os.path.abspath(p) for p in paths if os.path.exists(p)]
        if not valid_paths:
            return False
        
        try:
            if not self.headless:
                try:
                    logger.info(f"   [Multimedia] Pasting {len(valid_paths)} image(s) via clipboard...")
                    await self._paste_files_from_clipboard(valid_paths, page)
                    await asyncio.sleep(5) 
                    
                    if caption: 
                        await self._write_caption(caption, page)
                        await asyncio.sleep(0.5)
                    
                    await self._click_send()
                    return True
                except Exception as e:
                    logger.warning(f"   [!] Multimedia paste failed: {e}. Trying selector method...")

            logger.info("   [Multimedia] Using 'Photos & Videos' selector...")
            
            try:
                btn_adjuntar = page.locator(SEL_BTN_ADJUNTAR).first
                await btn_adjuntar.wait_for(state="visible", timeout=5000)
                await btn_adjuntar.click(force=True)
                await asyncio.sleep(0.8) 
            except Exception as e:
                raise e

            try:
                async with page.expect_file_chooser(timeout=10000) as fc_info:
                    btn_fotos_selectors = [
                        'span[data-icon="attach-image"]',
                        '[aria-label="Fotos y videos"]',
                        '[aria-label="Photos & Videos"]',
                        'li:has(span[data-icon="attach-image"])',
                        'button:has(span[data-icon="attach-image"])'
                    ]
                    
                    btn_fotos = None
                    for sel_f in btn_fotos_selectors:
                        try:
                            el = page.locator(sel_f).first
                            if await el.is_visible(timeout=500):
                                btn_fotos = el
                                break
                        except: continue
                    
                    if not btn_fotos:
                        btn_fotos = page.get_by_role("button").filter(has_text="Fotos y videos")
                    
                    await btn_fotos.click(force=True)
                
                file_chooser = await fc_info.value
                await file_chooser.set_files(valid_paths)
            except Exception as e:
                await page.keyboard.press("Escape")
                return False
            
            await asyncio.sleep(5)
            
            if caption: 
                await self._write_caption(caption, page)
                await asyncio.sleep(0.5)

            await self._click_send()
            return True

        except Exception as e:
            return False

    async def close(self):
        await self._clean_connection()

    async def _is_page_active(self) -> bool:
        try:
            return bool(self._page and not self._page.is_closed())
        except:
            return False
