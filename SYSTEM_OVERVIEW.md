## Emotion-Aware Smart Street Lighting – System Overview

This document describes the project end-to-end: **frontend (user login & dashboard)**, **backend (FastAPI APIs & auth)**, and **edge device (Raspberry Pi 4 + PCA9685 + sensors)**. It is written to be easy for both humans and AI tools to understand the full stack.

---

## 1. High-Level Architecture

- **Frontend** (`frontend/`)
  - Static HTML/CSS/JS served by the backend at `/frontend/`.
  - Provides:
    - Login page (`index.html` + `login.js`).
    - Dashboard page (`dashboard.html` + `dashboard.js`, `analytics.js`, `charts.js`).
  - Uses JWT auth (stored in `localStorage`) to call backend APIs and subscribe to a WebSocket stream of alerts.

- **Backend** (`backend/`)
  - FastAPI application exposing:
    - Login & user APIs (`/api/auth/*`).
    - Dashboard data APIs (`/api/events`, `/api/analytics`, `/api/advanced-analytics`, `/api/tower-status`, etc.).
    - Edge-only APIs secured with an API key (`/api/alert`, `/api/heartbeat`).
  - Stores events and tower status in SQLite (`backend/storage/database.db`).
  - Broadcasts new events to the dashboard WebSocket (`/ws/dashboard`).

- **Edge Device** (`edge_device/`)
  - Runs on **Raspberry Pi 4** or PC (simulation mode).
  - Captures video frames, runs emotion detection, decides risk & actions, then:
    - Controls **servo pan/tilt** (MG996R via PCA9685).
    - Controls **LED floodlight** via MOSFET on a GPIO pin.
    - Sends alerts + snapshots to backend `/api/alert` using an API key.
  - All hardware behavior is abstracted in `hardware_controller.py`.

---

## 2. Frontend Overview

> **Note**: The frontend has been modernized into a React + Vite Single Page Application (SPA) located in `frontend/src/` (`App.jsx`, `main.jsx`). Dependencies are managed via `package.json` and started using `npm run dev` (development) or `npm run build` (production). Below is the overview of the architecture and component flows.

### 2.1. Files

- `frontend/index.html`
  - Login page only (no dashboard markup).
  - Includes:
    - `style.css` – shared styling.
    - `analytics.js` – shared auth helpers (token storage, `fetchJson`, etc.).
    - `login.js` – handles login form & redirects.
  - Route: `http://<backend-host>:<port>/frontend/index.html` (shorthand `/frontend/`).

- `frontend/dashboard.html`
  - Dashboard UI:
    - Header with edge status, tower status badges, user info, logout button.
    - Summary cards: total events, high/medium/low risk counts.
    - Left column: real-time events list.
    - Right column: analytics charts + admin panel (reset DB).
  - Includes:
    - `style.css`
    - `https://cdn.jsdelivr.net/npm/chart.js`
    - `charts.js`
    - `analytics.js`
    - `dashboard.js`
  - Route: `http://<backend-host>:<port>/frontend/dashboard.html`.

- `frontend/login.js`
  - On page load:
    - Checks `localStorage` for token via `window.Analytics.getStoredToken()`.
    - Calls `window.Analytics.validateToken()`; if valid, redirects to `dashboard.html`.
  - On login form submit:
    - POST `/api/auth/login` (form-data: `username`, `password`).
    - On `200`:
      - Saves `access_token` and `role` via `window.Analytics.setAuthToken(...)`.
      - Logs `"login success"` to console.
      - Redirects to `dashboard.html`.
    - On `401`/`400`: shows “Invalid username or password.”.
    - On `429`: shows “Too many attempts, wait 60s before trying again.”.

- `frontend/dashboard.js`
  - On page load:
    - Initializes modals.
    - Wires **Logout** button (clears auth, tears down hardware polling, redirects to `index.html`).
    - Validates token with `/api/auth/me`; if valid, calls `initDashboard(user)`, else redirects back to `index.html`.
  - `initDashboard(user)`:
    - Shows dashboard and sets header text: `Logged in as <username> (<role>)`.
    - Shows/hides admin actions depending on `role === "admin"`.
    - Calls:
      - `loadInitialEvents()` → GET `/api/events?limit=50` via `Analytics.fetchJson`.
      - `Analytics.loadAnalytics()` → GET `/api/analytics`.
      - `Analytics.loadTowerStatus()` → GET `/api/tower-status`.
    - Opens WebSocket connection to `ws://<backend-host>/ws/dashboard`:
      - Logs `"websocket connected"`.
      - On `{"type": "new_alert", "event": ...}`: prepends event to list, refreshes analytics.
    - Schedules periodic refresh:
      - Analytics every 15s.
      - Tower status every 30s.
  - WebSocket reconnection logic:
    - Keeps exactly **one** WebSocket connection.
    - Auto-reconnects after close (while logged in).

- `frontend/analytics.js`
  - Token & role storage (localStorage):
    - `authToken` – JWT.
    - `authRole` – role string (e.g., `"admin"`, `"operator"`).
    - Also migrates from legacy keys: `emotion_dashboard_jwt`, `emotion_dashboard_role`.
  - Core API helper:
    - `fetchJson(url, options)`:
      - Adds `Authorization: Bearer <token>` when available.
      - On `401`:
        - Calls `clearAuth()`.
        - Calls `window.showLogin()` if defined.
        - Throws error.
  - Auth helpers:
    - `validateToken()` → calls `GET /api/auth/me`; logs `"token restored"` on success.
    - `clearAuth()` → clears token/role from memory & localStorage (including legacy keys).
  - Dashboard data loaders:
    - `loadAnalytics()` → `/api/analytics` (plus `/api/advanced-analytics` for events per hour).
    - `loadTowerStatus()` → `/api/tower-status`.

- `frontend/charts.js`
  - Wraps Chart.js to render/update:
    - Risk pie chart.
    - Emotion bar chart.
    - Events-per-hour line chart.

- `frontend/style.css`
  - Shared styles for:
    - Login page.
    - Dashboard layout, cards, tables, modals, buttons.

### 2.2. Frontend Auth Flow Summary

1. User visits `/frontend/` → `index.html` (login page).
2. If token is valid:
   - Frontend redirects to `/frontend/dashboard.html`.
3. On login:
   - POST `/api/auth/login` → `access_token`, `role`.
   - Save `authToken` + `authRole`.
   - Redirect to dashboard.
4. On dashboard load:
   - `/api/auth/me` verifies token.
   - If 200 → show dashboard and start loading data + WebSocket.
   - If 401 → redirect back to login and clear auth.
5. Any later `401` from `fetchJson` also clears auth and returns to login.

---

## 3. Backend Overview

### 3.1. Entry Point

- `backend/app.py`
  - FastAPI app + Uvicorn entry point (`python -m backend.app`).
  - Mounts:
    - API router (from `backend/routes.py`).
    - Static frontend at `/frontend/`.
    - WebSocket endpoint `/ws/dashboard`.

### 3.2. Key Modules

- `backend/routes.py`
  - Defines all HTTP endpoints.
  - Uses:
    - `jwt_handler` for JWT auth (dashboard & admin).
    - `api_key_auth` for edge endpoints (`/api/alert`, `/api/heartbeat`).
  - Talks to:
    - SQLite via `database.get_db`.
    - Analytics engine via `analytics_engine`.
    - WebSocket manager via `ws_manager`.

- `backend/auth/jwt_handler.py`
  - Hashes passwords, verifies login, creates and decodes JWTs.
  - `get_current_user` dependency used by protected routes.
  - `require_role("admin")` for strict admin-only endpoints.

- `backend/auth/api_key.py`
  - `api_key_auth` dependency:
    - Expects header: `X-API-KEY: <settings.API_KEY>`.
    - Rejects invalid/missing keys with 401.

- `backend/models.py`
  - Defines `Event` model and helpers to convert DB rows.

- `backend/database.py`
  - Returns `sqlite3` connections to `backend/storage/database.db`.

- `backend/websocket_manager.py`
  - Manages list of connected dashboard WebSocket clients.
  - Broadcasts `"new_alert"` events.

### 3.3. Important Endpoints

All endpoints are defined in `backend/routes.py`.

- **Health & metadata**
  - `GET /api/health`
    - No auth.
    - Returns DB status, websocket client count, event and tower stats, system version.

- **Dashboard data (JWT required)**
  - `GET /api/events?limit=100`
    - Auth: JWT (`Authorization: Bearer <token>`).
    - Returns latest events.
  - `GET /api/event/{event_id}`
  - `GET /api/analytics`
    - Basic counts + edge online flag + emotion distribution.
  - `GET /api/advanced-analytics`
    - Requires JWT (admin or operator by design).
    - Returns per-hour data used for charts.
  - `GET /api/tower-status`
    - Returns ONLINE/OFFLINE status for all towers.

- **Admin (JWT – admin only)**
  - `POST /api/admin/reset-database`
    - Auth: `require_role("admin")`.
    - Deletes all events.
  - `GET /api/admin/status`
    - Returns basic system stats for admin panel.

- **Auth (JWT)**
  - `POST /api/auth/register`
    - Registers new user.
    - Body: `username`, `password`, optional `role` (`"admin"` or `"operator"`, default `"operator"`).
  - `POST /api/auth/login`
    - Body: `username`, `password`.
    - Returns: `{"access_token", "token_type", "role"}`.
  - `GET /api/auth/me`
    - Returns basic user info: `{id, username, role}`.

- **Edge-only (API key)**
  - `POST /api/alert`
    - Auth: `X-API-KEY` header (must match backend `settings.API_KEY`).
    - Multipart form (`tower_id`, `location`, `event_type`, `emotion`, `confidence`, `timestamp`, optional `video`).
    - Stores event, triggers LLM analysis, writes to DB, and broadcasts over WebSocket.
  - `POST /api/heartbeat`
    - Auth: `X-API-KEY`.
    - Updates `tower_status` heartbeat row.

---

## 4. Edge Device Overview

### 4.1. Main Files

- `edge_device/edge_main.py`
  - Main loop for the edge device.
  - Responsibilities:
    - Logs startup info (tower ID, location).
    - Optionally checks for model updates (`model_update.check_and_update_model`).
    - Starts `EmotionModel` (face/emotion detection).
    - Creates `HardwareController` instance.
    - Opens camera (`cv2.VideoCapture(CAMERA_INDEX)`).
    - For every Nth frame (`FRAME_SKIP`):
      - Predicts emotion.
      - Uses `decision_engine.evaluate` to choose:
        - `risk_level`, `event_type`.
        - `led_brightness` (0–100).
        - `servo_angle` (0–180).
        - `send_alert` boolean.
      - Calls:
        - `hardware.set_led_brightness(led_brightness)`.
        - `hardware.set_servo_angle(servo_angle)`.
      - If `send_alert`:
        - Optionally save snapshot (`snapshot_manager.save_snapshot`).
        - Calls `alert_sender.send_alert` to `/api/alert`.

- `edge_device/hardware_controller.py`
  - New implementation using **PCA9685** + **GPIO MOSFET**.
  - API (unchanged from callers):
    - `set_servo_angle(angle_deg: int)` – 0–180 degrees.
    - `set_led_brightness(value_0_to_1: float)`:
      - Accepts float [0.0–1.0] **or** integer 0–100 (backwards compatible).
    - `cleanup()` – stops PWM, deinitializes PCA9685, cleans GPIO.
  - Behavior:
    - **Simulation mode (PC)**:
      - Triggered when `RUN_ON_RPI=false` or hardware libs fail to import.
      - No imports of `RPi.GPIO`, `busio`, `board`, or `PCA9685`.
      - Logs:
        - `[SIM] LED brightness -> X%`
        - `[SIM] Servo angle = Y°`
    - **Raspberry Pi mode (real hardware)**:
      - Servo:
        - Controlled via **PCA9685** on I2C (address `PCA9685_ADDRESS`, bus `PCA9685_I2C_BUS`).
        - Uses `SERVO_CHANNEL` (default 0).
        - Frequency: 50 Hz (`_SERVO_FREQUENCY_HZ`).
        - Pulse width range in microseconds:
          - `SERVO_MIN_PULSE_US` (default 500 µs → ~0°).
          - `SERVO_MAX_PULSE_US` (default 2500 µs → ~180°).
        - Converts angle → pulse µs → PCA9685 16-bit `duty_cycle`.
      - LED:
        - MOSFET gate on `LED_GPIO_PIN` (default BCM 18).
        - Initializes PWM:
          - `GPIO.setmode(GPIO.BCM)`
          - `GPIO.setup(LED_GPIO_PIN, GPIO.OUT)`
          - `GPIO.PWM(LED_GPIO_PIN, 1000)` (1 kHz).
        - Preferred: duty-cycle 0–100 via `ChangeDutyCycle`.
        - Fallback: direct HIGH/LOW if PWM fails.

- `edge_device/config.py`
  - Key environment-driven settings:
    - Backend:
      - `CENTRAL_SERVER_HOST` (default `"localhost"`).
      - `CENTRAL_SERVER_PORT` (default `"5000"`).
      - `CENTRAL_SERVER_SCHEME` (default `"http"`).
      - `ALERT_ENDPOINT` (default `http://<host>:<port>/api/alert`).
      - `API_KEY` – must match backend `settings.API_KEY`.
    - Tower identity:
      - `TOWER_ID` (e.g., `"TOWER_01"`).
      - `LOCATION` (e.g., `"Main_Street"`).
    - Camera:
      - `CAMERA_INDEX` (default `0`).
      - `FRAME_SKIP` (default `5`).
    - General:
      - `RUN_ON_RPI` (`"true"`/`"false"`).
      - `LOOP_INTERVAL_SECONDS` (optional delay between iterations).
    - Hardware:
      - `PCA9685_I2C_BUS` (default `1`).
      - `PCA9685_ADDRESS` (default `0x40`).
      - `SERVO_CHANNEL` (default `0`).
      - `SERVO_MIN_PULSE_US` (default `500`).
      - `SERVO_MAX_PULSE_US` (default `2500`).
      - `LED_GPIO_PIN` (default `18`).

- `edge_device/decision_engine.py`
  - Core decision logic mapping emotion + confidence → risk level, LED target, servo angle, and whether to send alert.

- `edge_device/alert_sender.py`
  - Builds multipart form and sends it to backend `/api/alert` with header:
    - `X-API-KEY: <API_KEY>`.

- `edge_device/test_hardware.py`
  - Simple script to test hardware or simulation:
    - LED brightness: 0%, 50%, 100%.
    - Servo sweep: 0° → 90° → 180° → 90°.

### 4.2. Hardware Wiring Summary

- **Raspberry Pi 4 → PCA9685**
  - Pi GPIO2 (SDA, pin 3) → PCA9685 SDA.
  - Pi GPIO3 (SCL, pin 5) → PCA9685 SCL.
  - Pi 5V (pin 2 or 4) → PCA9685 VCC.
  - Pi GND → PCA9685 GND.

- **PCA9685 → Servo (MG996R)**
  - Servo signal (usually yellow/orange) → PCA9685 **Channel 0** signal pin.
  - Servo V+ (red) → PCA9685 V+ (external 5V supply).
  - Servo GND (brown/black) → PCA9685 GND (shared with Pi GND).
  - In software:
    - `SERVO_CHANNEL = 0`.
    - `PCA9685_ADDRESS = 0x40`.
    - `SERVO_MIN_PULSE_US = 500`, `SERVO_MAX_PULSE_US = 2500` (adjustable).

- **LED Floodlight via MOSFET (IRLZ44N)**
  - **Drain** → LED negative terminal.
  - **Source** → GND (common ground with Pi & PCA9685).
  - **Gate** → Pi GPIO18 (BCM, pin 12) through a suitable resistor.
  - LED positive → external 12V/5V supply (appropriate to LED).
  - In software:
    - `LED_GPIO_PIN = 18`.
    - Controlled via `set_led_brightness(...)`.

- **Optional Sensors (not fully wired in code yet)**
  - **Light sensor (LM393 digital output)**:
    - DO pin → free GPIO input (e.g., BCM 23).
    - Could be integrated later to modulate LED brightness based on ambient light.
  - **PIR sensor (HC-SR501)**:
    - OUT pin → free GPIO input (e.g., BCM 24).
    - Could be integrated later to override LED on motion detection.

---

## 5. End-to-End Flow Summary

1. **User & admin management**
   - Use `POST /api/auth/register` to create `"admin"` and `"operator"` users.
   - Users log in via `/frontend/index.html`.
   - Admins see extra admin panel (Reset Database).

2. **Dashboard operation**
   - Frontend calls JWT-protected APIs, shows charts and events.
   - WebSocket streams new alerts and updates UI in real-time.

3. **Edge device operation**
   - Captures video and infers emotion.
   - Decides LED brightness and servo angle using `decision_engine`.
   - Controls servo via PCA9685 and LED via MOSFET on GPIO18.
   - Sends alerts to backend with `X-API-KEY`.
   - Dashboard receives events, stores them, and notifies all WebSocket clients.

This document should provide enough structure and cross-linking for an AI assistant (and human developers) to understand and navigate the project, from **user login** all the way down to **GPIO and PCA9685 hardware**.

