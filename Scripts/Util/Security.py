import os
import logging
from fastapi import Request, HTTPException
from typing import List

logger = logging.getLogger("Security")

class SecurityManager:

    def __init__(self, whatsapp_service=None):
        self.api_key = os.getenv("API_KEY_SECRETA", "demo_key")
        self.allowed_ips = [ip.strip() for ip in os.getenv("ALLOWED_IPS", "127.0.0.1").split(",")]
        self.ws = whatsapp_service

    async def verify(self, request: Request):
        client_ip = request.client.host
        
        if client_ip not in self.allowed_ips and "0.0.0.0" not in self.allowed_ips:
            logger.warning(f"ACCESS DENIED: Unauthorized connection attempt from IP: {client_ip}")
            raise HTTPException(status_code=403, detail=f"IP {client_ip} not authorized")

        api_key_header = request.headers.get("X-API-KEY")
        if api_key_header != self.api_key:
            logger.warning(f"INVALID API KEY: Unauthorized access attempt from {client_ip} with wrong key")
            raise HTTPException(status_code=401, detail="Invalid API Key")

        return True
