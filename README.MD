# Documentación Técnica: API de WhatsApp Automation

---

## Contenido
- [1. Introducción](#1-introducción)
    - [1.1 Objetivos](#11-objetivos)
    - [1.2 Alcance del Proyecto](#12-alcance-del-proyecto)
- [2. Marco Teórico](#2-marco-teórico)
    - [2.1 Automatización Web con Playwright](#21-automatización-web-con-playwright)
    - [2.2 APIs REST con FastAPI](#22-apis-rest-con-fastapi)
    - [2.3 Persistencia de Sesión](#23-persistencia-de-sesión-mediante-user-data-directory)
    - [2.4 Gestión de Memoria](#24-gestión-de-memoria-con-win32-api)
- [3. Análisis de Requerimientos](#3-análisis-de-requerimientos)
    - [3.1 Requerimientos Funcionales](#31-requerimientos-funcionales)
    - [3.2 Requerimientos No Funcionales](#32-requerimientos-no-funcionales)
- [4. Diseño y Arquitectura (UML 2.5)](#4-diseño-y-arquitectura-uml-25)
    - [4.1 Diagrama de Despliegue](#41-diagrama-de-despliegue)
    - [4.2 Diagrama de Actividad](#42-diagrama-de-actividad)
    - [4.3 Diagrama de Secuencia](#43-diagrama-de-secuencia)
    - [4.4 Modelo de Datos](#44-modelo-de-datos)
    - [4.5 Arquitectura de Seguridad](#45-arquitectura-de-seguridad)
- [5. Implementación](#5-implementación)
    - [5.1 Stack Tecnológico](#51-stack-tecnológico)
    - [5.2 Guía de Instalación y Despliegue](#52-guía-de-instalación-y-despliegue)
- [6. Pruebas (QA)](#6-pruebas-qa)
    - [6.1 Pruebas Unitarias y de Integración](#61-pruebas-unitarias-y-de-integración)
- [7. Conclusiones y Trabajo Futuro](#7-conclusiones-y-trabajo-futuro)
    - [7.1 Conclusiones](#71-conclusiones)
    - [7.2 Trabajo Futuro](#72-trabajo-futuro)

---


## 1. Introducción

Este documento describe la arquitectura, el diseño y la implementación del sistema de automatización de WhatsApp, un servicio API orientado a escalar la comunicación empresarial mediante peticiones HTTP simples y seguras. El sistema actúa como un puente entre cualquier aplicación externa y WhatsApp Web, controlando el navegador de forma programática.

### 1.1 Objetivos

**Objetivo General:**
Desarrollar una API REST robusta y estable que permita a sistemas externos enviar mensajes de texto y archivos multimedia a través de WhatsApp Web de forma automatizada, confiable y con control de recursos.

**Objetivos Específicos:**

| # | Objetivo | Responsable |
|---|----------|-------------|
| 1 | Crear una interfaz HTTP (FastAPI) que abstraiga la complejidad del control del navegador | `ApiPuenteWhatsApp.py` |
| 2 | Garantizar la persistencia de sesión para evitar el escaneo repetitivo del QR | Directorio `Storage/` |
| 3 | Verificar el destinatario real antes de confirmar el éxito del envío | `MacroWhatsApp._buscar_contacto()` |
| 4 | Controlar el consumo de RAM del navegador de forma automática | `MacroWhatsApp.verificar_y_limpiar_memoria()` |
| 5 | Registrar todas las operaciones con logs rotativos diarios | `TimedRotatingFileHandler` en `Logs/` |

### 1.2 Alcance del Proyecto

El sistema cubre el ciclo completo de una notificación automatizada:

1. **Recepción:** Acepta peticiones POST con autenticación por `API Key` y filtro de IPs.
2. **Localización:** Busca al contacto o grupo dentro de WhatsApp Web usando selectores dinámicos.
3. **Validación:** Confirma que el chat abierto corresponde al destinatario buscado.
4. **Envío:** Inyecta el texto y/o adjunta archivos locales.
5. **Respuesta:** Retorna el nombre real del destinatario confirmado por la UI.
6. **Mantenimiento:** Monitoriza la RAM del navegador cada 120 segundos en segundo plano.

**Fuera del alcance:** Recepción de mensajes entrantes, cifrado end-to-end, y gestión de múltiples sesiones de WhatsApp simultáneas.

---

## 2. Marco Teórico

El proyecto se sustenta en los siguientes conceptos y tecnologías:

### 2.1 Automatización Web con Playwright
Playwright es una biblioteca de Microsoft que permite controlar navegadores (Chromium, Firefox, WebKit) de forma programática. A diferencia de Selenium, utiliza el **Chrome DevTools Protocol (CDP)** directamente, lo que le da acceso a bajo nivel al navegador y permite adjuntar sesiones ya en ejecución mediante `connect_over_cdp()`. Esto es fundamental para este proyecto, ya que el navegador con la sesión de WhatsApp ya activa es controlado sin necesidad de un servidor WebDriver externo.

### 2.2 APIs REST con FastAPI
FastAPI es un framework web moderno y de alto rendimiento para Python basado en `asyncio`. Permite definir endpoints con tipado estático usando `Pydantic`, genera documentación automática en `/docs` y es completamente asíncrono, lo que permite gestionar múltiples peticiones concurrentes sin bloquear el hilo principal.

### 2.3 Persistencia de Sesión mediante User Data Directory
En lugar de abrir WhatsApp con un perfil de navegador vacío en cada ejecución, el sistema lanza el navegador apuntando a un directorio de datos de usuario (`Storage/`). Esto hace que las cookies y credenciales de WhatsApp se conserven entre reinicios, eliminando la necesidad de escanear el código QR más de una vez.

### 2.4 Gestión de Memoria con Win32 API
El sistema usa `ctypes` para llamar directamente a `EmptyWorkingSet` de la API de Windows (`psapi.dll`). Esta función libera las páginas de memoria del Working Set del proceso hacia el sistema operativo sin matar el proceso, lo que reduce el consumo de RAM visible sin interrumpir el servicio.

---

## 3. Análisis de Requerimientos

### 3.1 Requerimientos Funcionales

| ID | Descripción | Implementación |
|----|-------------|----------------|
| RF1 | Autenticar peticiones mediante cabecera `X-API-Key` | `verificar_seguridad()` en `ApiPuenteWhatsApp.py` |
| RF2 | Bloquear IPs no incluidas en la lista blanca `ALLOWED_IPS` | Middleware en `verificar_seguridad()` |
| RF3 | Enviar mensajes de texto a contactos por nombre | `MacroWhatsApp.mensaje(chat, texto)` |
| RF4 | Enviar mensajes a números de teléfono directos | `MacroWhatsApp.enviar()` detecta dígitos y usa URL directa |
| RF5 | Adjuntar y enviar archivos locales (imágenes, PDFs, etc.) | `MacroWhatsApp._enviar_archivo(ruta)` |
| RF6 | Confirmar el nombre real del destinatario desde la UI | `MacroWhatsApp._buscar_contacto()` lee el header del chat |
| RF7 | Exponer endpoint de estado del sistema | `GET /sistema` devuelve RAM, tareas activas y conexión |
| RF8 | Limitar peticiones a 20 por minuto por IP | `@limiter.limit("20/minute")` en `ApiPuenteWhatsApp.py` |

### 3.2 Requerimientos No Funcionales

**RNF1 - Rendimiento:**
El monitor de memoria se ejecuta cada **120 segundos** como una corutina en segundo plano (`asyncio.create_task`). Al detectar que el proceso `msedge.exe` asociado al puerto de depuración supera el límite `LIMITE_RAM_MB`, llama a `EmptyWorkingSet` sobre todos los procesos hijo del navegador para liberar memoria sin interrumpir la sesión.

**RNF2 - Seguridad:**
- Validación de `X-API-Key` en cada petición.
- Contador de intentos fallidos por IP: tras 5 fallos, se registra una alerta crítica en los logs.
- Lista blanca de IPs configurable desde `.env` (`ALLOWED_IPS`). Si se define como `*`, acepta cualquier IP.

**RNF3 - Disponibilidad:**
El script `VentaDeWhatsapp.py` actúa como un proceso guardian ("Watchdog") que mantiene el navegador abierto en segundo plano, listo en el puerto de depuración remota para ser controlado por la API.

**RNF4 - Trazabilidad:**
Los logs se escriben en `Logs/api.log` con rotación diaria automática (`TimedRotatingFileHandler`) y se conservan hasta 30 días de historial. El formato incluye timestamp, nivel, nombre del logger y mensaje.

---

### 4.1 Diagrama de Despliegue (Infraestructura)
Este diagrama ilustra la distribución física de los componentes entre el servidor de producción (origen), el servidor de pruebas (actuador Windows) y la nube de WhatsApp.

![Diagrama de Despliegue](./documentacion/image/DiagramaDespliqgue.png)

### 4.2 Diagrama de Actividad (Flujo de Envío)
Detalla la lógica paso a paso del proceso de envío, incluyendo la validación de seguridad y la manipulación del portapapeles.

![Diagrama de Actividad](./documentacion/image/DiagramaActividad.png)

### 4.3 Diagrama de Secuencia (Flujo Técnico)
Detalla la interacción entre el Cliente, la API y el motor de automatización.

![Diagrama de Secuencia](./documentacion/image/DiagramaDeSecuencia.png)


### 4.4 Modelo de Datos

**Payload de entrada (POST `/enviar-mensaje`):**
```json
{
  "chat": "Nombre del Contacto o Grupo",
  "mensaje": "El texto del mensaje a enviar.",
  "archivos": ["C:\\Users\\Usuario\\imagen.jpg"]
}
```
> El campo `archivos` es opcional. Si se omite, solo se envía el texto.
> 
> **Nota técnica (Python):** Para evitar errores con las barras invertidas de Windows (`\`), se recomienda enviar las rutas usando cadenas "raw" (ej: `r"C:\Carpeta\imagen.jpg"`) o escapando las barras (ej: `"C:\\Carpeta\\imagen.jpg"`).

**Ejemplo de múltiples archivos (Array):**
```json
{
  "chat": "Familia",
  "mensaje": "Aquí están las fotos del viaje",
  "archivos": [
    "C:\\Fotos\\paisaje.jpg",
    "C:\\Fotos\\cena.png",
    "C:\\Documentos\\itinerario.pdf"
  ]
}
```

**Uso correcto en Python (Raw Strings):**
```python
payload = {
    "chat": "Prueba",
    "mensaje": "Mensaje desde Python",
    "archivos": [
        r"C:\Fotos\paisaje.jpg",
        r"C:\Fotos\cena.png"
    ]
}
```

**Respuesta exitosa:**
```json
{
  "status": "success",
  "destinatario_confirmado": "Nombre Real Leído de WhatsApp"
}
```

**Respuesta de error:**
```json
{
  "detail": "Descripción del error producido."
}
```

**Respuesta de `GET /sistema`:**
```json
{
  "navegador_conectado": true,
  "api_ram_mb": 45.32,
  "edge_ram_total_mb": 312.88,
  "tareas_activas": 0,
  "limite_ram_configurado": 400
}
```

**Variables de entorno (`.env`):**

| Variable | Descripción | Valor de ejemplo |
|----------|-------------|------------------|
| `PUERTO_WHATSAPP` | Puerto CDP del navegador | `9222` |
| `PUERTO_API` | Puerto donde escucha FastAPI | `8000` |
| `API_KEY_SECRETA` | Clave de autenticación | `MamayatechJRL2026` |
| `LIMITE_RAM_MB` | Umbral para liberar memoria | `400` |
| `MODO_HEADLESS` | Mostrar/ocultar navegador | `False` |
| `ALLOWED_IPS` | IPs permitidas (`,` separadas) | `*` |

### 4.5 Arquitectura de Seguridad
El sistema implementa múltiples capas de protección para garantizar la integridad y disponibilidad del servicio:

*   **Autenticación por Token (API Key):** Se requiere la cabecera `X-API-Key` en cada petición POST. El token se valida contra la variable `API_KEY_SECRETA`, permitiendo un control de acceso sencillo pero efectivo.
*   **Filtrado de IPs (Whitelist):** El sistema solo procesa peticiones provenientes de las IPs autorizadas en `ALLOWED_IPS`. Cualquier intento desde una IP externa es bloqueado en la capa de middleware.
*   **Protección contra Fuerza Bruta:** Se monitorizan los intentos fallidos de autenticación por IP. Al detectar un comportamiento sospechoso (más de 5 fallos), el sistema registra una alerta crítica en los logs para su posterior bloqueo o auditoría.
*   **Limitación de Tasa (Rate Limiting):** Mediante la integración de `slowapi`, se restringe el flujo a 20 peticiones por minuto para prevenir que un uso abusivo sature el motor de Playwright.
*   **Seguridad en el Navegador:** El motor de automatización se comunica a través de un puerto de depuración local, aislando el entorno de navegación de ataques externos directos.

---

## 5. Implementación

### 5.1 Stack Tecnológico

| Componente | Tecnología | Versión |
|------------|------------|---------|
| Lenguaje | Python | 3.11+ |
| Framework Web | FastAPI + Uvicorn | `>=0.100` |
| Automatización | Playwright (Python) | `>=1.40` |
| Validación datos | Pydantic | `>=2.0` |
| Control de procesos | psutil | `>=5.9` |
| Configuración | python-dotenv | `>=1.0` |
| Rate Limiting | slowapi | `>=0.1` |
| Motor del navegador | Microsoft Edge (Chromium) | Cualquier versión moderna |

### 5.2 Guía de Instalación y Despliegue

**Paso 1: Clonar y preparar el entorno virtual**
```powershell
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
.\venv\Scripts\activate
```

**Paso 2: Instalar dependencias**
```powershell
pip install -r requirements.txt
playwright install chromium
```

**Paso 3: Configurar el archivo `.env`**
```env
PUERTO_WHATSAPP=9222
PUERTO_API=8000
API_KEY_SECRETA=TuClaveSecretaAqui
LIMITE_RAM_MB=400
MODO_HEADLESS=False
ALLOWED_IPS=*
```

**Paso 4: Primer uso — Escanear el código QR**
```powershell
# Solo la primera vez, para iniciar sesión
python .\Scripts\Util\Login.py
```
> Escanea el código QR con tu teléfono. La sesión se guardará en `Storage/` automáticamente.

**Paso 5: Iniciar el sistema (orden obligatorio)**
```powershell
# Terminal 1: Lanzar el motor del navegador
python .\Scripts\Src\VentaDeWhatsapp.py

# Terminal 2: Iniciar la API
python .\Scripts\Src\ApiPuenteWhatsApp.py
```

**Paso 6: Hacer una petición de prueba**
```powershell
curl -X POST http://localhost:8000/enviar-mensaje `
  -H "X-API-Key: TuClaveSecretaAqui" `
  -H "Content-Type: application/json" `
  -d '{"chat": "Nombre del Contacto", "mensaje": "Hola, esto es una prueba."}'
```

---

## 6. Pruebas (QA)

### 6.1 Pruebas Unitarias y de Integración

**Prueba 1: Validación de API Key**
- **Descripción:** Enviar una petición con una API Key incorrecta.
- **Resultado esperado:** `HTTP 403 - API Key inválida`.
- **Cómo probar:**
  ```powershell
  curl -X POST http://localhost:8000/enviar-mensaje -H "X-API-Key: CLAVE_INCORRECTA" ...
  ```

**Prueba 2: Bloqueo de IP no autorizada**
- **Descripción:** Configurar `ALLOWED_IPS=192.168.1.100` y hacer una petición desde otra IP.
- **Resultado esperado:** `HTTP 403 - IP no autorizada`.

**Prueba 3: Envío a contacto existente**
- **Descripción:** Enviar un mensaje de texto a un contacto cuyo nombre existe en WhatsApp.
- **Resultado esperado:** `HTTP 200 - {"status": "success", "destinatario_confirmado": "Nombre Real"}`.

**Prueba 4: Contacto no encontrado**
- **Descripción:** Enviar a un nombre que no existe en la lista de contactos.
- **Resultado esperado:** `HTTP 500` con detalle del error de validación del nombre.

**Prueba 5: Control de RAM**
- **Descripción:** Configurar `LIMITE_RAM_MB=1` para forzar la activación del limpiador.
- **Resultado esperado:** El log muestra `"RAM reducida de XXX MB a YYY MB"` y el proceso Edge continúa funcionando.

**Prueba 6: Rate Limiting**
- **Descripción:** Enviar más de 20 peticiones en un minuto desde la misma IP.
- **Resultado esperado:** A partir de la petición 21, se recibe `HTTP 429 - Too Many Requests`.

**Prueba 7: Endpoint de estado `/sistema`**
- **Descripción:** Llamar a `GET /sistema` sin autenticación.
- **Resultado esperado:** JSON con el estado actual de la RAM y la conexión al navegador.

---

## 7. Conclusiones y Trabajo Futuro

### 7.1 Conclusiones
El sistema desarrollado demuestra que es posible construir un servicio de mensajería automatizada estable y seguro usando tecnologías open-source modernas. La arquitectura de sesión persistente resuelve el principal problema práctico (el re-escaneo del QR) y el monitor de RAM garantiza que el servicio pueda ejecutarse de forma continua incluso en máquinas con recursos limitados. La validación del destinatario en tiempo real añade una capa de confiabilidad que distingue esta API de soluciones más simples.

### 7.2 Trabajo Futuro

| Mejora | Descripción | Prioridad |
|--------|-------------|-----------|
| **Webhook de entrada** | Capturar y reenviar mensajes recibidos a una URL externa | Alta |
| **Panel de control web** | Dashboard para visualizar logs y estado en tiempo real | Media |
| **Cola de mensajes** | Implementar una cola (Redis/RabbitMQ) para manejar picos de carga | Media |
| **Soporte multi-sesión** | Gestionar múltiples cuentas de WhatsApp en paralelo | Baja |
| **Integración con IA** | Respuestas automáticas inteligentes usando LLMs | Baja |
