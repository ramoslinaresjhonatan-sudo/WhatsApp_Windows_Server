# Technical Documentation: WhatsApp Automation API

---

## Contents
- [1. Introduction](#1-introduction)
    - [1.1 Objectives](#11-objectives)
    - [1.2 Project Scope](#12-project-scope)
- [2. Theoretical Framework](#2-theoretical-framework)
    - [2.1 Web Automation with Playwright](#21-web-automation-with-playwright)
    - [2.2 REST APIs with FastAPI](#22-rest-apis-with-fastapi)
    - [2.3 Session Persistence](#23-session-persistence-via-user-data-directory)
    - [2.4 Memory Management with psutil](#24-memory-management-with-psutil)
- [3. Requirements Analysis](#3-requirements-analysis)
    - [3.1 Functional Requirements](#31-functional-requirements)
    - [3.2 Non-Functional Requirements](#32-non-functional-requirements)
- [4. Design and Architecture](#4-design-and-architecture)
    - [4.4 Data Model and API Contracts](#44-data-model-and-api-contracts)
    - [4.5 Security Architecture](#45-security-architecture)
- [5. Implementation](#5-implementation)
    - [5.1 Tech Stack](#51-tech-stack)
    - [5.2 Installation and Deployment Guide](#52-installation-and-deployment-guide)
- [6. Testing (QA)](#6-testing-qa)
    - [6.1 Unit and Integration Testing](#61-unit-and-integration-testing)
- [7. Conclusions and Future Work](#7-conclusions-and-future-work)
    - [7.1 Conclusions](#71-conclusions)
    - [7.2 Future Work](#72-future-work)

---

## 1. Introduction

This document describes the architecture, design, and implementation of the WhatsApp automation system, a professional API service aimed at scaling business communication through simple and secure HTTP requests. The system acts as a bridge between any external application and WhatsApp Web, controlling the browser programmatically with strict recipient validation, resource monitoring, and active security alerts.

### 1.1 Objectives

**General Objective:**
Develop a robust and stable REST API that allows external systems to send text messages and multimedia files via WhatsApp Web in an automated, reliable way with resource control and active event notification.

**Specific Objectives:**

| # | Objective | Component |
|---|-----------|-----------|
| 1 | Create an HTTP interface (FastAPI) to abstract browser control complexity | `ApiPuenteWhatsApp.py` |
| 2 | Ensure session persistence to avoid repetitive QR scanning | `Storage/sesion_whatsapp/` directory |
| 3 | Verify the real recipient before confirming send success | `MacroWhatsApp._wait_for_chat_header()` |
| 4 | Automatically control browser RAM consumption safely | `MacroWhatsApp.check_and_clean_ram()` |
| 5 | Log all operations with daily rotating logs | `TimedRotatingFileHandler` in `Logs/` |
| 6 | Notify unauthorized access attempts in real-time via WhatsApp | `SecurityManager` + `ALERT_NUMBER` |

### 1.2 Project Scope

The system covers the complete cycle of an automated notification:

1.  **Reception:** Accepts POST requests with `API Key` authentication and IP filtering.
2.  **Queueing:** Enqueues the message and processes it sequentially to avoid browser conflicts.
3.  **Localization:** Searches for the contact or group within WhatsApp Web using dynamic selectors and smart waiting.
4.  **Strict Validation:** Confirms that the open chat title matches the requested recipient. If it doesn't match, the dispatch is aborted.
5.  **Sending:** Inyects text and/or attaches local files (images or documents).
6.  **Confirmation:** Verifies that the "pending" icon (clock) disappears before declaring success.
7.  **Maintenance:** Monitors browser RAM every 120 seconds in the background, waiting for zero active tasks to free resources.
8.  **Active Security:** If an unauthorized access attempt is detected (invalid IP or Key), the system automatically sends an alert to the number configured in `NUMERO_ALERTA`.

**Out of scope:** Incoming message reception, end-to-end encryption management (handled by WhatsApp), and multi-account management.

---

## 2. Theoretical Framework

### 2.1 Web Automation with Playwright
Playwright is a Microsoft library that allows programmatic control of browsers. Unlike Selenium, it uses the **Chrome DevTools Protocol (CDP)** directly, providing low-level access and allowing connection to already running sessions via `connect_over_cdp()`. The engine uses **smart waiting** (`wait_for_selector`, `is_visible`) instead of fixed sleeps, making the bot faster and more resilient.

### 2.2 REST APIs with FastAPI
FastAPI is a modern, high-performance web framework for Python based on `asyncio`. All requests are processed through an `asyncio.Queue` to ensure sequential and safe access to the browser instance.

### 2.3 Session Persistence via User Data Directory
The system launches the browser pointing to a specific user data directory (`Storage/sesion_whatsapp`). This ensures that WhatsApp cookies and credentials are preserved between restarts, eliminating the need to scan the QR code more than once.

### 2.4 Memory Management with psutil
The system uses `psutil` to monitor RAM consumption of both the API and the `msedge.exe` process (including all its children). If consumption exceeds `LIMITE_RAM_MB` and there are no active tasks (`_active_tasks == 0`), the system cleanly resets the CDP connection.

---

## 3. Requirements Analysis

### 3.1 Functional Requirements

| ID | Description | Implementation |
|----|-------------|----------------|
| RF1 | Authenticate requests via `X-API-Key` header (case-insensitive) | `SecurityManager.verify()` |
| RF2 | Block IPs not included in `ALLOWED_IPS` whitelist | `SecurityManager.verify()` |
| RF3 | Send text messages to contacts by name | `MacroWhatsApp.send(chat, message)` |
| RF4 | Attach and send local images with inline preview | `MacroWhatsApp._send_multimedia()` via clipboard |
| RF5 | Attach and send documents (PDF, etc.) | `MacroWhatsApp._send_files()` via file-chooser |
| RF6 | Confirm real recipient name reading the chat header | `MacroWhatsApp._wait_for_chat_header()` |
| RF7 | Abort dispatch if contact is not found | `MacroWhatsApp.send()` returns `False` if navigation fails |
| RF8 | Expose authenticated system status endpoint | `GET /system` |
| RF9 | Send security alert via WhatsApp on unauthorized access | `SecurityManager` + `_security_alert()` callback |

### 3.2 Non-Functional Requirements

**RNF1 - Performance:**
The memory monitor runs every **120 seconds**. It only acts when `_active_tasks == 0` to avoid interrupting a dispatch in progress.

**RNF2 - Security:**
- Case-insensitive `X-API-Key` validation.
- IP Whitelist in `.env`. `0.0.0.0` allows all IPs.
- **Active Alert:** On any blocked access attempt, a message is sent to `NUMERO_ALERTA`.

**RNF3 - Availability:**
The `VentaDeWhatsapp.py` script acts as a "Watchdog" process that keeps the browser open and clicks "Use here" if WhatsApp detects other active windows.

**RNF4 - Traceability:**
Daily rotating logs in `Logs/api.log` and `Logs/whatsapp.log`, kept for 30 days.

---

## 4. Design and Architecture

### 4.4 Data Model and API Contracts

**Endpoint: `POST /send-message`**

Input Payload:
```json
{
  "chat": "Contact or Group Name",
  "message": "The message text to send.",
  "files": ["C:\\Users\\User\\image.jpg"]
}
```
> Both `message` and `files` are optional, but at least one must be provided.

**Successful Response:**
```json
{
  "status": "success",
  "destination": "Contact or Group Name"
}
```

**System Status Response (`GET /system`):**
```json
{
  "browser_connected": true,
  "api_ram_mb": 45.32,
  "active_tasks": 0,
  "ram_limit_mb": 800,
  "queue_size": 0
}
```

**Environment Variables (`.env`):**

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `PUERTO_WHATSAPP` | Browser CDP Port | `9222` |
| `PUERTO_API` | FastAPI Port | `8000` |
| `API_KEY_SECRETA` | Authentication Key | `your_secret_key` |
| `LIMITE_RAM_MB` | Memory threshold | `800` |
| `MODO_HEADLESS` | Show/Hide browser | `false` |
| `ALLOWED_IPS` | Allowed IPs (comma separated). `0.0.0.0` = all | `127.0.0.1` |
| `NUMERO_ALERTA` | WhatsApp number for security alerts | `+1234567890` |

---

## 5. Implementation

### 5.2 Installation and Deployment Guide

**Quick Start (Windows — Recommended)**

The system includes automated scripts to simplify setup and execution:

1.  **Installation:** Run `INSTALAR_TODO.bat` (Double-click). This will create the virtual environment, install all dependencies, and set up the Playwright browser engines automatically.
2.  **Execution:** Run `INICIAR_TODO.bat` (Double-click). This will launch both the Browser Watchdog and the FastAPI Bridge in a single process.

---

**Manual Installation (Alternative)**

**Step 1: Setup virtual environment**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**Step 2: Install dependencies**
```powershell
pip install -r requirements.txt
playwright install msedge
```

**Step 3: Configure `.env` file**
Create a `.env` file based on `.env.example`.

**Step 4: First use — Scan QR Code**
```powershell
python .\Scripts\Util\Login.py
```

**Step 5: Start the system (Manual order)**
```powershell
# Terminal 1: Launch browser engine (Watchdog)
python .\Scripts\Src\VentaDeWhatsapp.py

# Terminal 2: Start the API
python .\Scripts\Src\ApiPuenteWhatsApp.py
```

**Step 6: Test request**
```powershell
curl -X POST http://localhost:8000/send-message `
  -H "X-API-Key: your_secret_key" `
  -H "Content-Type: application/json" `
  -d '{"chat": "Contact Name", "message": "Hello test."}'
```

---

## 6. Testing (QA)

**Test 1: API Key Validation**
- **Expected result:** `HTTP 401 - Invalid API Key`. Security alert sent to `NUMERO_ALERTA`.

**Test 2: IP Whitelist**
- **Expected result:** `HTTP 403 - IP X.X.X.X is not authorized`. Security alert sent to `NUMERO_ALERTA`.

**Test 3: Contact Not Found**
- **Expected result:** `HTTP 500`. Log shows `Recipient not found`. No message sent to wrong person.

---

# Ghost Process Cleanup:
Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue; Stop-Process -Name "msedge" -Force -ErrorAction SilentlyContinue