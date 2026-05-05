import os
import sys
import asyncio
from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, '.env'))

from Scripts.Util.MacroWhatsApp import MacroWhatsApp
from Scripts.Util.Security import SecurityManager
from Scripts.Util.Logger import setup_logger
from Config.Setting import configure_settings, limiter

logger = setup_logger("API", os.path.join(BASE_DIR, 'logs', 'api.log'))
app = FastAPI(title="WhatsApp Automation API")
configure_settings(app)

ws = MacroWhatsApp()
security = SecurityManager(whatsapp_service=ws)

mensaje_queue = asyncio.Queue()

async def monitorear_memoria_background():
    while True:
        try:
            await ws.verificar_y_limpiar_memoria()
        except Exception as e:
            logger.error(f"Error en monitor de memoria: {e}")
        await asyncio.sleep(120)

async def procesador_de_cola():
    logger.info("Procesador de cola de mensajes iniciado.")
    while True:
        chat, mensaje, archivos, future = await mensaje_queue.get()
        try:
            logger.info(f"Procesando mensaje en cola para: {chat}")
            
            if archivos:
                resultado = await ws.varios(chat, archivos, mensaje)
            else:
                resultado = await ws.mensaje(chat, mensaje)
            
            if not future.done():
                future.set_result(resultado)
            
            await asyncio.sleep(2.5) 
            
        except Exception as e:
            logger.error(f"Error en el worker de cola: {e}")
            if not future.done():
                future.set_exception(e)
        finally:
            mensaje_queue.task_done()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(monitorear_memoria_background())
    asyncio.create_task(procesador_de_cola())
    logger.info("Servicios de segundo plano iniciados.")

class MessageRequest(BaseModel):
    chat: str
    mensaje: str
    archivos: Optional[List[str]] = None

@app.post("/enviar-mensaje", dependencies=[Depends(security.verificar)])
async def api_enviar_mensaje(req: MessageRequest, request: Request):
    logger.info(f"Petición recibida de {request.client.host}. Encolando mensaje para '{req.chat}'")
    
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    
    await mensaje_queue.put((req.chat, req.mensaje, req.archivos, future))
    
    try:
        resultado = await asyncio.wait_for(future, timeout=300)
        
        if resultado:
            return {
                "status": "success", 
                "destinatario": req.chat,
                "info": "Mensaje procesado desde la cola",
                "cola_restante": mensaje_queue.qsize()
            }
        
        raise HTTPException(status_code=500, detail="El robot no pudo completar el envío del mensaje")
        
    except asyncio.TimeoutError:
        logger.warning(f"Timeout en cola para el chat: {req.chat}")
        raise HTTPException(status_code=504, detail="Tiempo de espera en cola agotado")
    except Exception as e:
        logger.error(f"Error procesando envío encolado: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sistema", dependencies=[Depends(security.verificar)])
async def api_sistema():
    import psutil
    
    api_proc = psutil.Process(os.getpid())
    api_ram = api_proc.memory_info().rss / (1024 * 1024)
    
    edge_ram = 0
    puerto_config = os.getenv("PUERTO_WHATSAPP", "9222")
    pids_automatizacion = set()
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if 'msedge' in proc.info['name'].lower():
            try:
                cmdline = proc.info.get('cmdline') or []
                if any(f"--remote-debugging-port={puerto_config}" in arg for arg in cmdline):
                    pids_automatizacion.add(proc.info['pid'])
                    p = psutil.Process(proc.info['pid'])
                    for child in p.children(recursive=True):
                        pids_automatizacion.add(child.pid)
            except: continue

    for pid in pids_automatizacion:
        try:
            p = psutil.Process(pid)
            edge_ram += p.memory_info().rss / (1024 * 1024)
        except: continue
            
    return {
        "navegador_conectado": await ws._pagina_activa(),
        "api_ram_mb": round(api_ram, 2),
        "edge_ram_total_mb": round(edge_ram, 2),
        "tareas_activas": ws._tareas_activas,
        "limite_ram_configurado": ws.limite_ram
    }

if __name__ == "__main__":
    import uvicorn
    puerto = int(os.getenv("PUERTO_API", "8000"))
    logger.info(f"Iniciando API en el puerto {puerto}...")
    uvicorn.run(app, host="0.0.0.0", port=puerto)
