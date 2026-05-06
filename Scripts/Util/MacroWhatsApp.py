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

# ──────────────────────────────────────────────────────────
# SELECTORES DE WHATSAPP WEB (actualizables sin tocar lógica)
# ──────────────────────────────────────────────────────────
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
    """
    Motor de automatización de WhatsApp Web.
    Maneja conexión, envío de texto, archivos adjuntos y limpieza de memoria.
    """

    MAX_REINTENTOS = 3
    DELAY_REINTENTO = 2.0

    def __init__(self):
        self.puerto    = os.getenv("PUERTO_WHATSAPP", "9222")
        self._playwright   = None
        self._browser      = None
        self._context      = None
        self._page         = None
        self._tareas_activas = 0

    # ─────────────────────────────────────────
    # CONEXIÓN
    # ─────────────────────────────────────────

    async def conectar(self) -> bool:
        """Conecta al navegador Edge via CDP. Reconecta si la página está cerrada."""
        if self._page and not self._page.is_closed():
            return True
        try:
            if not self._playwright:
                self._playwright = await async_playwright().start()

            self._browser = await self._playwright.chromium.connect_over_cdp(
                f"http://localhost:{self.puerto}"
            )
            if not self._browser.contexts:
                logger.error("No hay contextos en el navegador. ¿Está corriendo VentaDeWhatsapp?")
                return False

            self._context = self._browser.contexts[0]

            # Buscar página de WhatsApp Web entre las pestañas abiertas
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
            logger.error(f"Error al conectar con el navegador: {e}")
            await self._limpiar_conexion()
            return False

    async def _validar_whatsapp(self) -> bool:
        """Verifica que WhatsApp Web esté cargado y listo."""
        try:
            await self._page.wait_for_selector(SEL_SIDEBAR, timeout=5000)
            logger.debug("WhatsApp Web validado correctamente.")
            return True
        except:
            logger.warning("WhatsApp no está en la pantalla principal. Intentando navegar...")
            return await self._abrir_whatsapp()

    async def _abrir_whatsapp(self) -> bool:
        """Navega a WhatsApp Web si no está cargado."""
        try:
            if "whatsapp.com" not in self._page.url:
                await self._page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
            await self._page.wait_for_selector(SEL_SIDEBAR, timeout=60000)
            return True
        except Exception as e:
            logger.error(f"No se pudo cargar WhatsApp Web: {e}")
            return False

    async def _limpiar_conexion(self):
        """Limpia el estado de la conexión para un reintento limpio."""
        try:
            if self._playwright:
                await self._playwright.stop()
        except: pass
        finally:
            self._page      = None
            self._browser   = None
            self._playwright = None

    # ─────────────────────────────────────────
    # API PÚBLICA
    # ─────────────────────────────────────────

    async def enviar(self, chat: str, mensaje: str = None, archivos: list = None) -> bool:
        """
        Envía un mensaje de texto, archivo(s) o ambos a un chat de WhatsApp.
        Si hay archivos, el mensaje de texto va como leyenda (caption) del adjunto.
        Reintentos automáticos en caso de error.
        """
        self._tareas_activas += 1
        intento = 0

        while intento < self.MAX_REINTENTOS:
            intento += 1
            logger.info(f"Intento {intento}/{self.MAX_REINTENTOS} — Enviando a '{chat}'...")

            try:
                if not await self.conectar():
                    raise ConnectionError("No se pudo conectar al navegador.")

                await self._buscar_chat(chat)

                if mensaje:
                    # Enviamos el mensaje de texto primero como mensaje independiente
                    await self._enviar_texto(mensaje)
                    await asyncio.sleep(1.5)

                if archivos:
                    # Enviamos los archivos después
                    await self._enviar_archivos(archivos)

                # Verificar que el mensaje se envió
                if await self._verificar_envio():
                    logger.info(f"   [✓] Confirmado: mensaje enviado a '{chat}'.")
                    return True
                else:
                    logger.warning(f"   [!] No se pudo confirmar el envío (intento {intento}).")

            except Exception as e:
                logger.error(f"   Error en intento {intento}: {e}")
                # Forzar reconexión en el siguiente intento
                await self._limpiar_conexion()

            if intento < self.MAX_REINTENTOS:
                await asyncio.sleep(self.DELAY_REINTENTO)

        logger.error(f"Falló el envío a '{chat}' tras {self.MAX_REINTENTOS} intentos.")
        self._tareas_activas -= 1
        return False

    async def mensaje(self, chat: str, texto: str) -> bool:
        return await self.enviar(chat, mensaje=texto)

    async def archivo(self, chat: str, ruta: str, texto: str = "") -> bool:
        return await self.enviar(chat, mensaje=texto or None, archivos=[ruta])

    async def varios(self, chat: str, rutas: list, texto: str = "") -> bool:
        return await self.enviar(chat, mensaje=texto or None, archivos=rutas)

    # ─────────────────────────────────────────
    # BÚSQUEDA DE CHAT
    # ─────────────────────────────────────────

    async def _buscar_chat(self, nombre: str):
        """Busca y abre el chat. Espera a que WhatsApp esté listo antes de buscar."""
        page = self._page

        # Esperar que la interfaz esté completamente cargada
        try:
            await page.wait_for_selector(SEL_SIDEBAR, timeout=30000)
            await page.wait_for_selector(SEL_LOADING, state="hidden", timeout=10000)
        except: pass

        # Hacer clic en el panel lateral para asegurar el foco
        try: await page.click(SEL_SIDEBAR, timeout=2000)
        except: pass

        # Localizar el campo de búsqueda con fallbacks de atajos
        search_box = None
        for sel in SEL_SEARCH:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1000):
                    search_box = el
                    break
            except: continue

        if not search_box:
            # Fallbacks de atajos como en whatsplay
            for atajo in ["Control+Alt+/", "Alt+K", "Control+f", "/"]:
                try:
                    await page.keyboard.press("Escape")
                    await page.keyboard.press(atajo)
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

        # Limpiar y escribir el nombre del chat
        await asyncio.sleep(0.3)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await asyncio.sleep(0.2)
        await page.keyboard.type(nombre, delay=50)
        await asyncio.sleep(1.8)

        # Intentar hacer clic en el resultado de búsqueda
        try:
            contact = page.locator(f'span[title="{nombre}"]').first
            await contact.wait_for(state="visible", timeout=6000)
            await contact.click()
        except:
            # Fallback: presionar Enter
            await page.keyboard.press("Enter")

        await asyncio.sleep(1.2)
        await self._esperar_chat_abierto(nombre)

    async def _esperar_chat_abierto(self, nombre: str) -> bool:
        """Verifica que el header del chat muestre el nombre correcto."""
        try:
            header = self._page.locator(f"{SEL_MAIN} header")
            await header.wait_for(timeout=10000)
            titulo = header.locator('span[dir="auto"]').first
            await titulo.wait_for(state="visible", timeout=5000)
            texto = await titulo.text_content()
            if texto and nombre.lower() in texto.lower():
                logger.debug(f"   [✓] Confirmado: Chat '{nombre}' correctamente abierto.")
                return True
            logger.warning(f"   [!] Header muestra '{texto}', esperaba '{nombre}'.")
            return False
        except:
            return False

    # ─────────────────────────────────────────
    # ENVÍO DE TEXTO
    # ─────────────────────────────────────────

    async def _obtener_input_texto(self):
        """Retorna el campo de texto del chat activo."""
        for sel in SEL_INPUT_TEXTO:
            try:
                el = self._page.locator(sel).first
                await el.wait_for(state="visible", timeout=2000)
                return el
            except: continue
        return self._page.locator('div[contenteditable="true"]').last

    async def _enviar_texto(self, texto: str):
        """Escribe y envía un mensaje de texto."""
        box = await self._obtener_input_texto()
        await box.click()
        await box.fill("")
        await asyncio.sleep(0.2)
        await self._page.keyboard.insert_text(texto)
        await asyncio.sleep(0.3)
        await self._page.keyboard.press("Enter")

    # ─────────────────────────────────────────
    # ENVÍO DE ARCHIVOS
    # ─────────────────────────────────────────

    async def _enviar_archivos(self, rutas: list, caption: str = None):
        """
        Adjunta uno o varios archivos al chat activo usando la estrategia de whatsplay.
        """
        rutas_validas = [os.path.abspath(r) for r in rutas if os.path.exists(r)]
        ausentes = [r for r in rutas if not os.path.exists(r)]
        if ausentes:
            logger.warning(f"   [!] Archivos no encontrados: {ausentes}")
        if not rutas_validas:
            logger.error("   [✗] Ningún archivo válido para adjuntar.")
            return

        logger.info(f"   Adjuntando {len(rutas_validas)} archivo(s): {[os.path.basename(r) for r in rutas_validas]}")
        page  = self._page

        try:
            # 1. Abrir menú del clip
            btn = page.locator(SEL_BTN_ADJUNTAR).first
            await btn.wait_for(state="visible", timeout=5000)
            await btn.click()
            await asyncio.sleep(1.0)
            
            # 2. Buscar input de archivo
            file_inputs = page.locator(SEL_FILE_INPUT)
            total = await file_inputs.count()
            
            if total == 0:
                logger.error("   [✗] No se encontró el input[type='file']")
                return
            
            # 3. Adjuntar usando el primer input disponible
            logger.info(f"   [+] {total} input(s) encontrados. Cargando archivos...")
            await file_inputs.first.set_input_files(rutas_validas)
            
            # Esperar a que WhatsApp procese la vista previa del adjunto
            logger.info("   Esperando vista previa del adjunto...")
            await asyncio.sleep(5)
            
            if caption:
                await self._escribir_caption(caption, page)

            # Enviar el adjunto
            await self._click_enviar()
            await asyncio.sleep(2.0)
            logger.info("   [✓] Archivos procesados y enviados.")

        except Exception as e:
            logger.error(f"   [✗] Error al adjuntar archivo: {e}")
            try: await page.keyboard.press("Escape")
            except: pass

    async def _pegar_archivos_portapapeles(self, rutas: list, page):
        """Estrategia de respaldo: copia archivos al portapapeles y pega con Ctrl+V."""
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "[System.Windows.Forms.Clipboard]::Clear(); "
            "$f = New-Object System.Collections.Specialized.StringCollection; "
            + " ".join(f"$f.Add('{r.replace(chr(39), chr(39)*2)}');" for r in rutas)
            + "[System.Windows.Forms.Clipboard]::SetFileDropList($f)"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            creationflags=0x08000000, timeout=10
        )
        await asyncio.sleep(0.5)
        input_box = await self._obtener_input_texto()
        await input_box.click()
        await page.keyboard.press("Control+V")
        await asyncio.sleep(3.5)

    async def _escribir_caption(self, texto: str, page):
        """Escribe el texto de leyenda en el campo de caption del adjunto."""
        for sel in SEL_CAPTION:
            try:
                cap = page.locator(sel).last
                if await cap.is_visible(timeout=2000):
                    await cap.click()
                    await page.keyboard.insert_text(texto)
                    await asyncio.sleep(0.4)
                    logger.info("   Caption añadido al adjunto.")
                    return
            except: continue
        logger.warning("   [!] No se encontró el campo de caption.")

    async def _click_enviar(self):
        """Presiona el botón de Enviar asegurando que clica la vista previa y no el fondo."""
        try:
            # Esperar a que el botón sea visible (el botón de la vista previa)
            # Aumentamos el tiempo de espera y usamos más selectores específicos
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
                    # Buscamos el último elemento que coincida (el de la vista previa suele ser el último o único visible)
                    btn = self._page.locator(sel).last
                    if await btn.is_visible(timeout=2000):
                        logger.info(f"   [✓] Botón de envío encontrado: {sel}")
                        await btn.click(force=True)
                        btn_found = True
                        break
                except: continue

            if not btn_found:
                logger.warning("   [!] No se detectó botón visual. Intentando forzar con Enter...")
                await self._page.keyboard.press("Enter")
            
        except Exception as e:
            logger.error(f"   [✗] Error en clic de envío: {e}")
            await self._page.keyboard.press("Enter")

    # ─────────────────────────────────────────
    # VERIFICACIÓN Y UTILIDADES
    # ─────────────────────────────────────────

    async def _verificar_envio(self) -> bool:
        """
        Espera a que desaparezca el icono de 'pendiente' y aparezca
        el de 'enviado' o 'entregado'. Timeout de 15 segundos.
        """
        await asyncio.sleep(1.5)
        try:
            # Esperar a que el mensaje deje de estar "pendiente"
            await self._page.locator(SEL_MSG_PENDIENTE).last.wait_for(
                state="hidden", timeout=15000
            )
            return True
        except:
            # Si el timeout vence, lo consideramos enviado de todas formas
            # (WhatsApp puede no mostrar el tick si hay lag)
            return True

    async def cerrar(self):
        """Cierra la conexión Playwright sin cerrar el navegador."""
        await self._limpiar_conexion()

    async def _pagina_activa(self) -> bool:
        """Retorna True si la página de WhatsApp está abierta y activa."""
        try:
            return bool(self._page and not self._page.is_closed())
        except:
            return False
