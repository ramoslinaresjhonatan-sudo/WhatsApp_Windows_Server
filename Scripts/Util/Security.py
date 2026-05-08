import logging
# pyrefly: ignore [missing-import]
from fastapi import Request, HTTPException

from Config.Setting import AppConfig

logger = logging.getLogger("Security")


class SecurityManager:

    def __init__(self, alert_callback=None):
        self._api_key: str = AppConfig.API_KEY
        self._allowed_ips: list[str] = AppConfig.ALLOWED_IPS
        self._alert_callback = alert_callback

    async def verify(self, request: Request) -> None:
        client_ip: str = request.client.host  

        if "0.0.0.0" not in self._allowed_ips and client_ip not in self._allowed_ips:
            logger.warning("ACCESS DENIED — unauthorized IP: %s", client_ip)
            if self._alert_callback and AppConfig.ALERT_NUMBER:
                await self._alert_callback(f"Security Alert: Unauthorized access attempt from IP {client_ip}")
            raise HTTPException(status_code=403, detail=f"IP {client_ip} is not authorized")

        provided_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key", "")
        if provided_key != self._api_key:
            logger.warning("INVALID API KEY — bad key from IP: %s", client_ip)
            if self._alert_callback and AppConfig.ALERT_NUMBER:
                await self._alert_callback(f"Security Alert: Invalid API Key used from IP {client_ip}")
            raise HTTPException(status_code=401, detail="Invalid API Key")
