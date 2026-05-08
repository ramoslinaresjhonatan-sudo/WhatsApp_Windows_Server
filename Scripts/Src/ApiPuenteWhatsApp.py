import os
import sys
import asyncio
import psutil
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

load_dotenv(_BASE_DIR / ".env")

from Config.Setting import AppConfig
from Scripts.Util.Logger import setup_logger
from Scripts.Util.MacroWhatsApp import MacroWhatsApp
from Scripts.Util.Security import SecurityManager

logger = setup_logger("API-Bridge", "api.log")

_ws = MacroWhatsApp()


async def _security_alert(msg: str):
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    await _message_queue.put((AppConfig.ALERT_NUMBER, msg, None, future))


_security = SecurityManager(alert_callback=_security_alert)


class MessageRequest(BaseModel):
    chat: str
    message: Optional[str] = None
    files: Optional[List[str]] = None


_message_queue: asyncio.Queue = asyncio.Queue()


async def _memory_monitor() -> None:
    while True:
        try:
            await _ws.check_and_clean_ram()
        except Exception as exc:
            logger.warning("Memory monitor iteration failed: %s", exc)
        await asyncio.sleep(120)


async def _queue_processor() -> None:
    logger.info("Queue processor ready.")
    while True:
        chat, msg, files, future = await _message_queue.get()
        try:
            logger.info("Processing queued message for: %s", chat)
            result = await _ws.send(chat, msg, files)
            future.set_result(result)
        except Exception as exc:
            logger.error("Queue processing error: %s", exc)
            future.set_result(False)
        finally:
            _message_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_memory_monitor())
    asyncio.create_task(_queue_processor())
    yield
    await _ws.close()


app = FastAPI(title="WhatsApp API Bridge", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.post("/send-message")
async def api_send_message(req: MessageRequest, request: Request):
    await _security.verify(request)

    if not req.message and not req.files:
        raise HTTPException(status_code=400, detail="Must provide 'message' or 'files'.")

    logger.info(
        "Request from %s — queuing message for '%s'.",
        request.client.host, req.chat,  
    )

    loop = asyncio.get_running_loop()
    future = loop.create_future()
    await _message_queue.put((req.chat, req.message, req.files, future))

    success = await future
    if success:
        return {"status": "success", "destination": req.chat}
    raise HTTPException(status_code=500, detail="Failed to send message.")


@app.get("/system")
async def api_system(request: Request):
    await _security.verify(request)
    try:
        proc = psutil.Process(os.getpid())
        api_ram = proc.memory_info().rss / (1024 * 1024)
        return {
            "browser_connected": await _ws.connect(),
            "api_ram_mb": round(api_ram, 2),
            "active_tasks": _ws._active_tasks,
            "ram_limit_mb": _ws.ram_limit,
            "queue_size": _message_queue.qsize(),
        }
    except psutil.NoSuchProcess as exc:
        return {"error": str(exc)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=AppConfig.API_PORT)
