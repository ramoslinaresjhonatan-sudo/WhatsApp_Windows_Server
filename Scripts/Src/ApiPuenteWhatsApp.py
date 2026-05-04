import os
import sys
import asyncio
from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

# Configuración de Rutas y Entorno
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Importaciones del Proyecto
from Scripts.Util.MacroWhatsApp import MacroWhatsApp
from Scripts.Util.Security import SecurityManager
from Scripts.Util.Logger import setup_logger
from Config.Setting import configure_settings, limiter

# 1. Inicialización de Componentes Core
logger = setup_logger("API", os.path.join(BASE_DIR, 'logs', 'api.log'))
app = FastAPI(title="WhatsApp Automation API")
configure_settings(app)

ws = MacroWhatsApp()
security = SecurityManager(whatsapp_service=ws)

# 2. Tareas en Segundo Plano (Background Services)
async def monitorear_memoria_background():
    """Vigila el consumo de RAM del navegador y limpia si es necesario."""
    while True:
        try:
            await ws.verificar_y_limpiar_memoria()
        except Exception as e:
            logger.error(f"Error en monitor de memoria: {e}")
        await asyncio.sleep(120)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(monitorear_memoria_background())
    logger.info("Monitor de memoria iniciado en segundo plano.")

# 3. Modelos de Datos
class MessageRequest(BaseModel):
    chat: str
    mensaje: str
    archivos: Optional[List[str]] = None

# 4. Endpoints (Rutas de la API)
@app.post("/enviar-mensaje", dependencies=[Depends(security.verificar)])
@limiter.limit("20/minute")
async def api_enviar_mensaje(req: MessageRequest, request: Request):
    """Recibe una orden de envío y la procesa a través del robot."""
    logger.info(f"Petición de {request.client.host}: Enviar a '{req.chat}'")
    try:
        if req.archivos:
            resultado = await ws.varios(req.chat, req.archivos, req.mensaje)
        else:
            resultado = await ws.mensaje(req.chat, req.mensaje)
            
        if resultado:
            nombre_final = resultado if isinstance(resultado, str) else req.chat
            return {"status": "success", "destinatario_confirmado": nombre_final}
        
        raise HTTPException(status_code=500, detail="Error en envío: El robot no pudo completar la acción")
    
    except Exception as e:
        logger.error(f"Error procesando envío: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # NO llamamos a ws.cerrar() aquí.
        # Desconectar Playwright inmediatamente después de dar Enter hace que el navegador
        # aborte la subida del archivo en curso. Mantendremos la conexión viva.
        pass

@app.get("/sistema", dependencies=[Depends(security.verificar)])
async def api_sistema():
    """Devuelve el estado actual de salud y recursos del servidor."""
    import psutil
    
    # Memoria de la API
    api_proc = psutil.Process(os.getpid())
    api_ram = api_proc.memory_info().rss / (1024 * 1024)
    
    # Memoria del Navegador (Edge)
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

# 5. Ejecución
if __name__ == "__main__":
    import uvicorn
    puerto = int(os.getenv("PUERTO_API", "8000"))
    logger.info(f"Iniciando API en el puerto {puerto}...")
    uvicorn.run(app, host="0.0.0.0", port=puerto)
