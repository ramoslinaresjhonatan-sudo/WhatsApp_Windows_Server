import os
import time
import psutil
import ctypes
import logging
from playwright.sync_api import sync_playwright

logger = logging.getLogger("BrowserManager")

class BrowserManager:

    def __init__(self, user_data_dir, puerto="9222", headless=False, limite_ram_mb=400):
        self.user_data_dir = user_data_dir
        self.puerto = puerto
        self.headless = headless
        self.limite_ram = limite_ram_mb

    def reducir_memoria(self):
        pids_validos = set()
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if 'msedge' in proc.info['name'].lower():
                try:
                    cmdline = proc.info.get('cmdline') or []
                    if any(f"--remote-debugging-port={self.puerto}" in arg for arg in cmdline):
                        pids_validos.add(proc.info['pid'])
                        p = psutil.Process(proc.info['pid'])
                        for child in p.children(recursive=True):
                            pids_validos.add(child.pid)
                except: continue
        
        for pid in pids_validos:
            try:
                handle = ctypes.windll.kernel32.OpenProcess(0x001F0FFF, False, pid)
                if handle:
                    ctypes.windll.psapi.EmptyWorkingSet(handle)
                    ctypes.windll.kernel32.CloseHandle(handle)
            except: pass

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
                    args=[
                        f"--remote-debugging-port={self.puerto}",
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-infobars",
                        "--mute-audio"
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
                    page.goto(url)
                
                while True:
                    self.reducir_memoria()
                    time.sleep(120)
                    
            except Exception as e:
                logger.error(f"Error en el ciclo del navegador: {e}")
            finally:
                logger.info("Cerrando manager de navegador...")
