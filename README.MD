# WhatsApp Automation API - Documentación Técnica

Este sistema actúa como un puente entre aplicaciones externas y WhatsApp Web, permitiendo el envío automatizado de mensajes y archivos mediante peticiones HTTP seguras.

---

## 🚀 Contenido
- [1. Introducción](#1-introducción)
- [2. Marco Teórico](#2-marco-teórico)
- [3. Análisis de Requerimientos](#3-análisis-de-requerimientos)
- [4. Diseño y Arquitectura](#4-diseño-y-arquitectura)
- [5. Implementación](#5-implementación)
- [6. Guía de Uso de la API](#6-guía-de-uso-de-la-api)
- [7. Pruebas y Seguridad](#7-pruebas-y-seguridad)

---

## 1. Introducción
**Objetivo:** Desarrollar una API REST robusta que permita a sistemas externos enviar mensajes a través de WhatsApp Web de forma automatizada y confiable.

### Funcionalidades principales:
- Interfaz HTTP (FastAPI) para control remoto.
- Persistencia de sesión (evita escanear QR cada vez).
- Verificación de destinatario real desde la interfaz de WhatsApp.
- Gestión automática de memoria RAM.

---

## 2. Marco Teórico
El proyecto se sustenta en tres pilares tecnológicos:
- **FastAPI:** Framework asíncrono de alto rendimiento para la gestión de la API.
- **Playwright:** Motor de automatización que controla el navegador mediante el protocolo CDP.
- **Win32 API:** Interfaz de bajo nivel utilizada para liberar memoria RAM del sistema de forma preventiva.

---

## 3. Análisis de Requerimientos
- **Funcionales:** Envío de texto, envío de multimedia (imágenes, PDFs), validación de nombre de contacto y reporte de estado del sistema.
- **No Funcionales:** Seguridad por API Key, limitación de peticiones (20/min), registro de logs rotativos y persistencia de datos.

---

## 4. Diseño y Arquitectura
### Estructura del Proyecto
```
Scripts/
├── Src/
│   ├── ApiPuenteWhatsApp.py   # API Principal (FastAPI)
│   └── VentaDeWhatsapp.py     # Gestor del Navegador (Guardian)
└── Util/
    ├── MacroWhatsApp.py       # Lógica del Robot de Automatización
    ├── Security.py            # Gestión de Seguridad y Baneos
    ├── Logger.py              # Sistema de Logs Rotativos
    └── Login.py               # Script para Inicio de Sesión (QR)
```

---

## 5. Implementación
### Instalación y Despliegue
1. **Dependencias:** `pip install -r requirements.txt`
2. **Navegador:** `playwright install chromium`
3. **Sesión:** Iniciar sesión una única vez con `python Scripts/Util/Login.py`.

### Ejecución
1. Iniciar el navegador: `python Scripts/Src/VentaDeWhatsapp.py`
2. Iniciar la API: `python Scripts/Src/ApiPuenteWhatsApp.py`

---

## 6. Guía de Uso de la API
### Autenticación
Todas las peticiones requieren la cabecera: `X-API-Key: <TU_API_KEY_SECRETA>`

### Endpoints Principales

#### **POST `/enviar-mensaje`**
Envía mensajes de texto y/o archivos multimedia.

**Ejemplo de Petición (CURL):**
```bash
curl -X POST http://localhost:8000/enviar-mensaje \
     -H "X-API-Key: TU_CLAVE_SECRETA" \
     -H "Content-Type: application/json" \
     -d '{
          "chat": "Nombre del Contacto",
          "mensaje": "Hola, esto es un mensaje de prueba",
          "archivos": ["C:\\ruta\\al\\archivo.jpg"]
         }'
```

**Ejemplo de Petición (Python):**
```python
import requests

url = "http://localhost:8000/enviar-mensaje"
headers = {
    "X-API-Key": "TU_CLAVE_SECRETA",
    "Content-Type": "application/json"
}
payload = {
    "chat": "75055472",  # Puede ser nombre o número
    "mensaje": "Mensaje desde Python",
    "archivos": [r"C:\Fotos\imagen.jpg"]  # Ejemplo con raw string (r"")
}

response = requests.post(url, json=payload, headers=headers)
print(response.json())
```

**Ejemplo de Petición (JavaScript/Web):**
```javascript
const response = await fetch("http://localhost:8000/enviar-mensaje", {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-API-Key': 'TU_CLAVE_SECRETA'
    },
    body: JSON.stringify({
        chat: "Nombre del Contacto",
        mensaje: "Mensaje desde la WEB",
        archivos: []
    })
});
console.log(await response.json());
```

> **💡 Nota para Windows:** Al enviar rutas de archivos, asegúrate de usar doble barra diagonal (`"C:\\Carpeta\\archivo.jpg"`) en el JSON, o usar cadenas crudas (`r"C:\Carpeta\archivo.jpg"`) si estás programando en Python para evitar errores de escape.

- **GET `/sistema`**: Devuelve métricas de RAM y estado de conexión (requiere `X-API-Key`).

---

## 7. Pruebas y Seguridad
### Capas de Protección
- **Timing Attacks:** Protección en la comparación de llaves de seguridad.
- **Baneo de IP:** Bloqueo automático de 15 minutos tras 5 intentos fallidos.
- **Alertas:** Notificación inmediata vía WhatsApp al detectar un ataque.
- **Logs:** Historial completo de operaciones en la carpeta `Logs/`.

---
© 2026 WhatsApp Automation System - Documentación Coherente para Producción.
