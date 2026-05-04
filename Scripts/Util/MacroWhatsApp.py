import os
import sys
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

class MacroWhatsApp:
    def __init__(self):
        self.puerto = os.getenv("PUERTO_WHATSAPP", "9222")
        self.limite_ram = int(os.getenv("LIMITE_RAM_MB", "512"))
        
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._tareas_activas = 0

    async def conectar(self):
        if self._page and not self._page.is_closed():
            return True

        try:
            if not self._playwright:
                self._playwright = await async_playwright().start()
            
            self._browser = await self._playwright.chromium.connect_over_cdp(f"http://localhost:{self.puerto}")
            
            if not self._browser.contexts:
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
            return await self._validar_whatsapp()

        except Exception as e:
            logger.error(f"Error conectando: {e}")
            await self.cerrar()
            return False

    async def _validar_whatsapp(self):
        try:
            await self._page.wait_for_selector('div#side', timeout=5000)
            return True
        except:
            return await self._abrir_whatsapp()

    async def _abrir_whatsapp(self):
        if "whatsapp.com" not in self._page.url:
            await self._page.goto("https://web.whatsapp.com")
        try:
            await self._page.wait_for_selector('div#side', timeout=60000)
            return True
        except:
            return False

    async def enviar(self, chat, mensaje=None, archivos=None):
        self._tareas_activas += 1
        if not await self.conectar():
            self._tareas_activas -= 1
            return False
        try:
            await self._buscar_chat(chat)

            if mensaje:
                await self._enviar_texto(mensaje)
                await asyncio.sleep(1)

            if archivos:
                await self._enviar_archivos(archivos)

            await self._esperar_envio()
            return True
        except Exception as e:
            logger.error(f"Error en envío: {e}")
            return False
        finally:
            self._tareas_activas -= 1

    async def _buscar_chat(self, nombre):
        page = self._page
        try:
            await page.wait_for_selector('#side', timeout=30000)
            await page.wait_for_selector('div[data-testid="loading"]', state="hidden", timeout=10000)
        except: pass

        search_selectors = [
            '#side div[contenteditable="true"]',
            'div[contenteditable="true"][data-tab="3"]',
            'div[data-testid="chat-list-search"]',
            'div[role="textbox"][aria-placeholder*="Busc"]',
            'div[role="textbox"][aria-label*="Busc"]'
        ]
        
        try: await page.click('#side', timeout=2000)
        except: pass

        try:
            await page.keyboard.press("Control+Alt+/")
            await asyncio.sleep(0.8)
        except: pass

        search = None
        for sel in search_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible():
                    search = el
                    break
            except: continue
                
        if search:
            try: await search.click(force=True)
            except: pass

        await asyncio.sleep(0.5)
        
        await page.keyboard.press('Control+A')
        await page.keyboard.press('Backspace')
        await asyncio.sleep(0.3)

        await page.keyboard.type(nombre, delay=60)
        await asyncio.sleep(2.0)

        chat_selector = f'span[title="{nombre}"]'
        try:
            contact = page.locator(chat_selector).first
            await contact.wait_for(state="visible", timeout=7000)
            await contact.click()
        except:
            await page.keyboard.press('Enter')

        await asyncio.sleep(1.5)
        await self._esperar_chat_abierto(nombre)

    async def _esperar_chat_abierto(self, nombre):
        try:
            header = self._page.locator('#main header')
            await header.wait_for(timeout=10000)
            titulo_elemento = header.locator('span[dir="auto"]').first
            await titulo_elemento.wait_for(state="visible", timeout=5000)
            titulo_actual = await titulo_elemento.text_content()
            if titulo_actual and nombre.lower() in titulo_actual.lower():
                return True
            return False
        except: return False

    async def _input_chat(self):
        selectores = [
            'div.lexical-rich-text-input div[contenteditable="true"]',
            'div[data-testid="conversation-compose-box-input"]',
            'div[contenteditable="true"][data-tab="10"]',
            '#main footer div[contenteditable="true"]',
            'div[title="Escribe un mensaje"]',
            'footer div[role="textbox"]'
        ]
        for sel in selectores:
            try:
                el = self._page.locator(sel).first
                await el.wait_for(state="visible", timeout=3000)
                return el
            except: continue
        return self._page.locator('div[contenteditable="true"]').last

    async def _enviar_texto(self, texto):
        box = await self._input_chat()
        await box.click()
        await box.fill("")
        await self._page.keyboard.insert_text(texto)
        await self._page.keyboard.press("Enter")

    async def _copiar_archivos_al_portapapeles(self, rutas):
        script_lines = [
            "Add-Type -AssemblyName System.Windows.Forms",
            "[System.Windows.Forms.Clipboard]::Clear()",
            "$files = New-Object System.Collections.Specialized.StringCollection"
        ]
        for r in rutas:
            abs_path = os.path.abspath(r).replace("'", "''")
            script_lines.append(f"$files.Add('{abs_path}')")
        script_lines.append("[System.Windows.Forms.Clipboard]::SetFileDropList($files)")
        ps_code = "; ".join(script_lines)
        cmd = ["powershell", "-NoProfile", "-Command", ps_code]
        try: subprocess.run(cmd, creationflags=0x08000000)
        except: pass

    async def _enviar_archivos(self, rutas, mensaje=None):
        rutas_validas = [r for r in rutas if os.path.exists(r)]
        if not rutas_validas: return

        page = self._page
        input_box = await self._input_chat()
        await input_box.click()
        await asyncio.sleep(0.5)

        await self._copiar_archivos_al_portapapeles(rutas_validas)
        await asyncio.sleep(0.8)

        await page.keyboard.press("Control+V")
        await asyncio.sleep(3.5)

        if mensaje:
            caption_selectors = [
                'div[data-tab="10"]',
                'div[data-tab="6"]',
                'div[contenteditable="true"][role="textbox"]',
            ]
            for sel in caption_selectors:
                try:
                    cap = page.locator(sel).last
                    if await cap.is_visible():
                        await cap.click()
                        await page.keyboard.insert_text(mensaje)
                        await asyncio.sleep(0.5)
                        break
                except: continue

        await self._click_enviar()
        await asyncio.sleep(2.0)

    async def _click_enviar(self):
        try:
            btn = self._page.locator('span[data-icon="send"]').last
            await btn.click()
        except:
            await self._page.keyboard.press("Enter")

    async def _esperar_envio(self):
        await asyncio.sleep(2)
        try:
            await self._page.locator('span[data-icon="msg-time"]').wait_for(state="hidden", timeout=10000)
        except: pass

    async def mensaje(self, chat, texto):
        return await self.enviar(chat, mensaje=texto)

    async def archivo(self, chat, ruta, texto=""):
        return await self.enviar(chat, mensaje=texto, archivos=[ruta])

    async def varios(self, chat, rutas, texto=""):
        return await self.enviar(chat, mensaje=texto, archivos=rutas)

    async def cerrar(self):
        try:
            if self._playwright: await self._playwright.stop()
        except: pass
        finally:
            self._page = None
            self._browser = None
            self._playwright = None

    async def verificar_y_limpiar_memoria(self):
        if self._tareas_activas > 0: return
        pids = set()
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if 'msedge' in proc.info['name'].lower():
                try:
                    cmdline = proc.info.get('cmdline') or []
                    if f"--remote-debugging-port={self.puerto}" in str(cmdline):
                        pids.add(proc.info['pid'])
                        p = psutil.Process(proc.info['pid'])
                        for child in p.children(recursive=True): pids.add(child.pid)
                except: continue
        if not pids: return
        for pid in pids:
            try:
                handle = ctypes.windll.kernel32.OpenProcess(0x001F0FFF, False, pid)
                if handle:
                    ctypes.windll.psapi.EmptyWorkingSet(handle)
                    ctypes.windll.kernel32.CloseHandle(handle)
            except: pass

    async def _pagina_activa(self):
        try: return self._page and not self._page.is_closed()
        except: return False
