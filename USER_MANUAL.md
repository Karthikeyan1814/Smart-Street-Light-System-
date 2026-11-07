## Emotion-Aware Smart Street Lighting – User Manual

This manual explains how to:

- Start the **backend & frontend**.
- Create users and log in to the dashboard.
- Configure and run the **edge device** (Raspberry Pi).
- Send example **POST requests** from the Pi to the backend.

It is written so that both humans and AI tools can follow the steps.

---

## 1. Backend & Frontend

### 1.1. Prerequisites

- Python 3.9+ installed (for backend).
- Node.js 18+ and npm installed (for frontend).
- Project root:  
  `D:\Smart-street-light-project`

#### Install Backend Dependencies:

```powershell
cd D:\Smart-street-light-project
python -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

#### Install Frontend Dependencies:

```powershell
cd D:\Smart-street-light-project\frontend
npm install
```

### 1.2. Start the Backend

From the project root, with the virtualenv activated:

```powershell
.\backend\.venv\Scripts\Activate.ps1
python -m backend.app
```

The backend starts listening on **port 5000** (`http://localhost:5000`).

### 1.3. Start and Open the Frontend

The frontend is a React + Vite application. You can run it in development mode (recommended) or build it for production.

#### Option A: Development Mode (Recommended)

In a new terminal window:

```powershell
cd D:\Smart-street-light-project\frontend
npm run dev
```

Then open your browser to:
`http://localhost:5173`

> **Note**: If you recently installed Node.js, ensure you close and re-open your terminal or IDE so that `node` and `npm` are loaded into your environment PATH.

#### Option B: Production Build (Served via FastAPI backend)

1. Build the frontend assets:
   ```powershell
   cd D:\Smart-street-light-project\frontend
   npm run build
   ```
2. With the backend running (`python -m backend.app`), open:
   `http://localhost:5000/frontend/`

---

## 2. Users, Roles, and Login

### 2.1. Roles

The system supports at least two roles:

- **admin**
  - Full access.
  - Can use admin panel (Reset Database).
  - Can access advanced analytics and admin endpoints.

- **operator**
  - Can log in and see the dashboard and analytics.
  - No access to admin-only actions.

### 2.2. Create Users (via API)

Endpoint: `POST /api/auth/register`

- **Body (form-data)**:
  - `username`: string (required).
  - `password`: string (required).
  - `role`: `"admin"` or `"operator"` (optional, default `"operator"`).

Example (PowerShell / Windows, using `curl`):

```powershell
curl -X POST "http://localhost:5000/api/auth/register" ^
  -F "username=admin1" ^
  -F "password=YourStrongPassword" ^
  -F "role=admin"
```

Example (Linux/macOS):

```bash
curl -X POST "http://localhost:5000/api/auth/register" \
  -F "username=operator1" \
  -F "password=YourStrongPassword" \
  -F "role=operator"
```

### 2.3. Login from the Browser

1. Open: `http://localhost:5173` (or `http://localhost:5000/frontend/` if using the built frontend).
2. Enter `username` and `password` of a registered user (or the bypass credentials if configured).
3. On success, proceed to the device connection screen and enter the edge device IP to access the dashboard.
4. On the dashboard:
   - Monitor real-time telemetry, emotion distribution, and alert logs.
   - Operators and Admins can interact with the system controls according to their role.

To **log out**, click the **Logout** button on the dashboard.

---

## 3. Edge Device (Raspberry Pi 4)

### 3.1. Hardware Summary

- **Board**: Raspberry Pi 4.
- **Servo**: MG996R connected via **PCA9685** (I2C).
- **LED Floodlight**: Controlled by IRLZ44N MOSFET driven from a Pi GPIO pin.
- Sensors (optional, not fully used in code yet):
  - Light sensor (LM393).
  - PIR (HC-SR501).

#### 3.1.1. Wiring – PCA9685 & Servo

- Raspberry Pi → PCA9685:
  - Pi GPIO2 (SDA, pin 3) → PCA9685 SDA.
  - Pi GPIO3 (SCL, pin 5) → PCA9685 SCL.
  - Pi 5V (pin 2 or 4) → PCA9685 VCC.
  - Pi GND → PCA9685 GND.

- PCA9685 → MG996R Servo:
  - Servo signal → PCA9685 Channel 0 signal pin.
  - Servo V+ (red) → PCA9685 V+ (driven by external 5V).
  - Servo GND → PCA9685 GND (shared with Pi).

#### 3.1.2. Wiring – LED Floodlight via MOSFET

- IRLZ44N MOSFET:
  - Drain → LED negative.
  - Source → GND (common with Pi and PCA9685).
  - Gate → Raspberry Pi **GPIO18** (BCM) via resistor (~220 Ω recommended).
  - LED positive → external power supply (as required by LED).

#### 3.1.3. Optional Sensors

These are not fully integrated into the current code but can be wired as:

- Light sensor (LM393, digital output):
  - DO → free GPIO (e.g., BCM 23).
  - VCC → 3.3V or 5V per module.
  - GND → GND.

- PIR sensor (HC-SR501):
  - OUT → free GPIO (e.g., BCM 24).
  - VCC → 5V.
  - GND → GND.

### 3.2. Edge Software Install

On the Raspberry Pi, install dependencies for the edge device:

```bash
cd /path/to/emotion-aware-smart-street-lighting/edge_device
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`edge_device/requirements.txt` includes:

- Core: `opencv-python`, `numpy`, `requests`, `psutil`.
- Pi hardware:
  - `RPi.GPIO`
  - `adafruit-blinka`
  - `adafruit-circuitpython-pca9685`
  - `smbus2`

### 3.3. Edge Configuration – Environment Variables

On the Pi, before running the edge code:

```bash
export CENTRAL_SERVER_HOST="192.168.137.198"   # backend IP
export CENTRAL_SERVER_PORT="5000"             # backend port
export CENTRAL_SERVER_SCHEME="http"
export API_KEY="dev-edge-api-key-change-me"   # must match backend
export RUN_ON_RPI="true"                      # enable real hardware
export TOWER_ID="TOWER_01"
export LOCATION="Main_Street"

# Optional hardware overrides (defaults shown):
export PCA9685_I2C_BUS="1"
export PCA9685_ADDRESS="0x40"
export SERVO_CHANNEL="0"
export SERVO_MIN_PULSE_US="500"
export SERVO_MAX_PULSE_US="2500"
export LED_GPIO_PIN="18"
```

On Windows/PowerShell, use:

```powershell
$env:CENTRAL_SERVER_HOST = "192.168.137.198"
$env:CENTRAL_SERVER_PORT = "5000"
$env:CENTRAL_SERVER_SCHEME = "http"
$env:API_KEY = "dev-edge-api-key-change-me"
$env:RUN_ON_RPI = "true"
$env:TOWER_ID = "TOWER_01"
$env:LOCATION = "Main_Street"
```

### 3.4. Test Hardware (or Simulation)

From `edge_device/`:

```bash
python test_hardware.py
```

What it does:

- Sets LED brightness to 0%, 50%, 100% (with 1-second delay between).
- Moves servo smoothly 0° → 90° → 180° → 90°.

If `RUN_ON_RPI=false` (simulation mode), it only logs e.g.:

- `[SIM] LED brightness -> 50%`
- `[SIM] Servo angle = 90°`

### 3.5. Run the Edge Main Loop

From `edge_device/`:

```bash
python edge_main.py
```

The edge device will:

1. Optionally check for updated emotion model from backend.
2. Open the camera (`CAMERA_INDEX`).
3. Loop over frames:
   - Run emotion detection.
   - Decide:
     - `led_brightness` (0–100).
     - `servo_angle` (0–180).
     - Whether to send an alert.
   - Call:
     - `hardware.set_led_brightness(led_brightness)`.
     - `hardware.set_servo_angle(servo_angle)`.
   - If sending alert:
     - Save snapshot (for high risk).
     - POST to backend `/api/alert` with `X-API-KEY`.

You can monitor behavior on the backend dashboard in real time.

---

## 4. Example POST from Pi (or Any Client)

This section shows concrete examples of sending an alert to the backend and how login works at the HTTP level.

### 4.1. Edge → Backend: POST /api/alert

**Endpoint**:  
`POST http://<CENTRAL_SERVER_HOST>:<CENTRAL_SERVER_PORT>/api/alert`

- Auth:
  - Header: `X-API-KEY: <API_KEY>`.

- Body (multipart/form-data):
  - `tower_id`: e.g. `"TOWER_01"`.
  - `location`: e.g. `"Main_Street"`.
  - `event_type`: e.g. `"Emergency"`.
  - `emotion`: e.g. `"Fear"`.
  - `confidence`: e.g. `0.92`.
  - `timestamp`: ISO8601 string (or omitted to use server time).
  - `video`: optional snapshot file (image; field name `video`).

Example `curl` from the Pi:

```bash
curl -X POST "http://192.168.137.198:5000/api/alert" \
  -H "X-API-KEY: dev-edge-api-key-change-me" \
  -F "tower_id=TOWER_01" \
  -F "location=Main_Street" \
  -F "event_type=Emergency" \
  -F "emotion=Fear" \
  -F "confidence=0.95" \
  -F "timestamp=2026-03-02T12:00:00Z" \
  -F "video=@/path/to/snapshot.jpg"
```

Example using Python `requests`:

```python
import requests

url = "http://192.168.137.198:5000/api/alert"
headers = {
    "X-API-KEY": "dev-edge-api-key-change-me",
}
data = {
    "tower_id": "TOWER_01",
    "location": "Main_Street",
    "event_type": "Emergency",
    "emotion": "Fear",
    "confidence": "0.95",
    "timestamp": "2026-03-02T12:00:00Z",
}
files = {
    # optional: remove this key if you do not send a snapshot
    "video": open("/path/to/snapshot.jpg", "rb"),
}

resp = requests.post(url, headers=headers, data=data, files=files)
print(resp.status_code, resp.json())
```

When this request succeeds:

- Backend writes the event into SQLite.
- LLM analysis runs to compute risk level & summary.
- WebSocket server broadcasts `{"type": "new_alert", "event": ...}` to all dashboards.

### 4.2. User Login: POST /api/auth/login

**Endpoint**:  
`POST http://<backend-host>:5000/api/auth/login`

- Body (form-data or x-www-form-urlencoded):
  - `username`
  - `password`

Example `curl`:

```bash
curl -X POST "http://localhost:5000/api/auth/login" \
  -F "username=admin1" \
  -F "password=YourStrongPassword"
```

Typical response:

```json
{
  "access_token": "<JWT_TOKEN>",
  "token_type": "bearer",
  "role": "admin"
}
```

The frontend stores this token and uses it in:

- Header: `Authorization: Bearer <JWT_TOKEN>`

for all requests to:

- `/api/events`
- `/api/analytics`
- `/api/advanced-analytics`
- `/api/tower-status`
- `/api/admin/*`

### 4.3. Verify Login: GET /api/auth/me

Example:

```bash
curl -X GET "http://localhost:5000/api/auth/me" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

Response:

```json
{
  "id": 1,
  "username": "admin1",
  "role": "admin"
}
```

This is the same endpoint the frontend uses on page load to decide whether to show the login page or dashboard.

---

## 5. How to Run Everything (Quick Checklist)

1. **Backend**
   - Activate virtualenv.
   - `python -m backend.app` (default port 5000).

2. **Create Users**
   - `POST /api/auth/register` to create `admin1` / `operator1`.

3. **Frontend**
   - In a new terminal: `cd frontend && npm run dev`
   - Visit `http://localhost:5173`.
   - Log in with your registered user or credentials.

4. **Edge Device (Pi)**
   - Set environment variables (host, port, API key, RUN_ON_RPI).
   - `pip install -r edge_device/requirements.txt`.
   - (Optional) `python edge_device/test_hardware.py`.
   - `python edge_device/edge_main.py`.

5. **Observe Dashboard**
   - Connect edge device IP and view dashboard.
   - Watch events list, charts, and tower status update as the edge device sends alerts and heartbeats.

This manual gives you concrete, end-to-end steps to run the system, log in as a user, and connect the Raspberry Pi edge device so that everything works together.

---

## 6. Firewall Configuration (Allow Edge Device to Laptop)

If the edge device cannot send alerts or upload videos to the laptop backend, Windows Firewall is likely blocking incoming TCP port 5000 connections.

Run the following command in an **Administrator Command Prompt** or **Administrator PowerShell**:

### Using `netsh` (Command Prompt / PowerShell):
```cmd
netsh advfirewall firewall add rule name="Smart Streetlight Backend Port 5000" dir=in action=allow protocol=TCP localport=5000
```

### Using PowerShell cmdlet:
```powershell
New-NetFirewallRule -DisplayName "Smart Streetlight Backend Port 5000" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
```
