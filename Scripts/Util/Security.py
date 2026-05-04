import os
import time
import logging
import secrets
import asyncio
from fastapi import Request, Header, HTTPException

logger = logging.getLogger("Security")

class SecurityManager:
    """
    Clase de seguridad robusta con alertas automáticas vía WhatsApp.
    """
    def __init__(self, whatsapp_service=None):
        self.allowed_ips = os.getenv("ALLOWED_IPS", "*").split(",")
        self.api_key_secreta = os.getenv("API_KEY_SECRETA", "CLAVE_POR_DEFECTO_CAMBIAME")
        self.nro_alerta = os.getenv("NUMERO_ALERTA")
        self.ws = whatsapp_service # Referencia al robot de WhatsApp
        self.failed_attempts = {}
        self.banned_ips = {}
        self.ban_duration = 900 # 15 minutos

    async def verificar(self, request: Request, x_api_key: str = Header(None, alias="X-API-Key")):
        client_ip = request.client.host
        ahora = time.time()

        # 1. Verificar Baneo
        if client_ip in self.banned_ips:
            desbloqueo = self.banned_ips[client_ip]
            if ahora < desbloqueo:
                raise HTTPException(status_code=429, detail="Demasiados intentos fallidos.")
            else:
                del self.banned_ips[client_ip]
                self.failed_attempts[client_ip] = 0

        # 2. Validar Whitelist IP
        if "*" not in self.allowed_ips and client_ip not in self.allowed_ips:
            logger.warning(f"Intento de acceso bloqueado: IP {client_ip} no autorizada.")
            raise HTTPException(status_code=403, detail=f"IP no autorizada: {client_ip}")

        # 3. Validar API Key
        if not secrets.compare_digest(x_api_key or "", self.api_key_secreta):
            intentos = self.failed_attempts.get(client_ip, 0) + 1
            self.failed_attempts[client_ip] = intentos
            
            logger.warning(f"INTENTO FALLIDO ({intentos}/5) desde IP: {client_ip}")

            if intentos >= 5:
                self.banned_ips[client_ip] = ahora + self.ban_duration
                logger.critical(f"IP BANEADA: {client_ip} bloqueada por 15 minutos.")
                
                # ENVIAR ALERTA POR WHATSAPP
                if self.ws and self.nro_alerta:
                    mensaje_alerta = (
                        f"*ALERTA DE SEGURIDAD*\n\n"
                        f"Se ha detectado un ataque de fuerza bruta.\n"
                        f"*IP:* {client_ip}\n"
                        f"*Estado:* Bloqueada por 15 minutos.\n"
                        f"*Hora:* {time.strftime('%H:%M:%S')}"
                    )
                    # Lo lanzamos como una tarea de fondo para no bloquear la respuesta de la API
                    asyncio.create_task(self.ws.mensaje(self.nro_alerta, mensaje_alerta))

                raise HTTPException(status_code=429, detail="Múltiples fallos. IP bloqueada.")
            
            raise HTTPException(status_code=403, detail="Credenciales inválidas.")
        
        if client_ip in self.failed_attempts:
            self.failed_attempts[client_ip] = 0
