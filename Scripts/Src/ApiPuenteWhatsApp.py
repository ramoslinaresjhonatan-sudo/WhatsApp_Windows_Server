import os
import sys
import asyncio
import logging
import psutil
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from contextlib import asynccontextmanager
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

load_dotenv(os.path.join(BASE_DIR, '.env'))

from Scripts.Util.Logger import setup_logger
from Scripts.Util.MacroWhatsApp import MacroWhatsApp
from Scripts.Util.Security import SecurityManager

logger = setup_logger("API-Bridge", "api.log")
ws = MacroWhatsApp()
security = SecurityManager(ws)

class MessageRequest(BaseModel):
    chat: str
    message: Optional[str] = None
    files: Optional[List[str]] = None

class CaptureRequest(BaseModel):
    chat: str
    html: str
    caption: Optional[str] = None

message_queue = asyncio.Queue()

async def monitor_memory_background():
    while True:
        try:
            await ws.check_and_clean_ram()
        except: pass
        await asyncio.sleep(120)

async def queue_processor():
    logger.info("   Queue processor started. Ready for messages.")
    while True:
        chat, msg, files, future = await message_queue.get()
        try:
            logger.info(f"Processing queued message for: {chat}")
            success = await ws.send(chat, msg, files)
            future.set_result(success)
        except Exception as e:
            logger.error(f"Error processing queue: {e}")
            future.set_result(False)
        finally:
            message_queue.task_done()

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(monitor_memory_background())
    asyncio.create_task(queue_processor())
    yield
    await ws.close()

app = FastAPI(title="WhatsApp API Bridge", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/send-message")
async def api_send_message(req: MessageRequest, request: Request):
    await security.verify(request)
    
    if not req.message and not req.files:
        raise HTTPException(status_code=400, detail="Must provide message or files")

    logger.info(f"Request received from {request.client.host}. Queuing message for '{req.chat}'")
    
    future = asyncio.get_event_loop().create_future()
    await message_queue.put((req.chat, req.message, req.files, future))
    
    success = await future
    if success:
        return {"status": "success", "destination": req.chat}
    else:
        raise HTTPException(status_code=500, detail="Failed to send message")

@app.post("/send-capture")
async def api_send_capture(req: CaptureRequest, request: Request):
    await security.verify(request)
    
    logger.info(f"Capture request for '{req.chat}'")
    success = await ws.send_capture(req.chat, req.html, req.caption)
    
    if success:
        return {"status": "success", "destination": req.chat}
    else:
        raise HTTPException(status_code=500, detail="Failed to send capture")

@app.get("/system")
async def api_system(request: Request):
    try:
        proc = psutil.Process(os.getpid())
        api_ram = proc.memory_info().rss / (1024 * 1024)
        
        return {
            "browser_connected": await ws.connect(),
            "api_ram_mb": round(api_ram, 2),
            "active_tasks": ws._active_tasks,
            "ram_limit_mb": ws.ram_limit
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PUERTO_API", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
