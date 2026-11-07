"""
alert_sender.py
Packages JSON metadata and dispatches it over HTTP to the central hub.
Handles heartbeat and distinct event alerts.
"""
import logging
import requests
import time
import threading

import config

logger = logging.getLogger(__name__)

class AlertSender:
    def __init__(self):
        self.session = requests.Session()
        
    def _send_async(self, url, payload, files=None, callback=None):
        def task():
            # Guard: silently skip if auto-discovery hasn't replaced the placeholder yet
            if "[IP_ADDRESS]" in url:
                return
            try:
                headers = {"X-API-KEY": config.API_KEY}
                if files:
                    # Flatten dict so python requests can send it as Form-Data
                    form_data = {k: str(v) for k, v in payload.items()}
                    # (connect_timeout=5s, read_timeout=60s) — MP4 uploads need time over WiFi
                    res = self.session.post(url, data=form_data, files=files, headers=headers, timeout=(5, 60))
                else:
                    # Form-Data strictly required by FastAPI `Form(...)` fields
                    form_data = {k: str(v) for k, v in payload.items()}
                    res = self.session.post(url, data=form_data, headers=headers, timeout=(5, 15))
                    
                if res.status_code not in (200, 201):
                    logger.warning(f"Failed to push to {url}. Status: {res.status_code}")
                elif callback:
                    try:
                        callback(res.json())
                    except Exception as parse_e:
                        logger.error(f"Error parsing response from {url}: {parse_e}")
            except Exception as e:
                logger.error(f"Network error dispatching to {url}: {e}")

        threading.Thread(target=task, daemon=True).start()

    def send_heartbeat(self, status_dict):
        raw_payload = {
            "tower_id": config.TOWER_ID,
            "device_online": True,
            "version": "4.0.0-final",
            "timestamp": __import__('datetime').datetime.utcnow().isoformat() + "Z",
            **status_dict
        }
        
        # FastAPI often rejects payloads if unexpected fields are provided (Extra.forbid)
        allowed_fields = ["tower_id", "device_online", "version", "timestamp"]
        payload = {k: v for k, v in raw_payload.items() if k in allowed_fields}
        
        def handle_heartbeat_response(data):
            if "override_mode" in data:
                mode = data["override_mode"]
                if mode in ["AUTO", "DAY", "NIGHT"] and getattr(config, "OVERRIDE_MODE", None) != mode:
                    config.OVERRIDE_MODE = mode
                    logger.info(f"Received new Edge Behavior Mode from dashboard: {mode}")
                    
            if "override_mosfet" in data:
                mosfet_mode = data["override_mosfet"]
                if mosfet_mode in ["AUTO", "FULL"] and getattr(config, "OVERRIDE_MOSFET", None) != mosfet_mode:
                    config.OVERRIDE_MOSFET = mosfet_mode
                    logger.info(f"Received new Mosfet Mode from dashboard: {mosfet_mode}")

        self._send_async(config.HEARTBEAT_ENDPOINT, payload, callback=handle_heartbeat_response)

    def send_event(self, event_data, snapshot_path=None):
        raw_payload = {
            "tower_id": config.TOWER_ID,
            "location": config.LOCATION,
            "timestamp": __import__('datetime').datetime.utcnow().isoformat() + "Z",
            **event_data
        }
        
        # FastAPI often rejects Form-Data if unexpected fields are provided.
        allowed_fields = [
            "tower_id", "location", "event_type", "emotion", "confidence",
            "emotion_confidence", "risk_level", "timestamp",
            # Phase 2 behavioral fields
            "gesture_detected", "activity", "threat_tags", "emotion_group",
        ]
        payload = {k: v for k, v in raw_payload.items() if k in allowed_fields}
        
        # Phase 1: Send metadata IMMEDIATELY with no file.
        # This ensures the dashboard updates at once regardless of video upload speed.
        self._send_async(config.EVENTS_ENDPOINT, payload, files=None)
        logger.info(f"Dispatched Event [{payload.get('event_type')}] Risk: {payload.get('risk_level')}")
        
        # Phase 2: Upload the video/snapshot in a separate background thread.
        # IMPORTANT: uses its own Session (NOT self.session) to avoid thread-safety issues
        # where Phase 1 and Phase 2 fight over the shared connection pool.
        if snapshot_path:
            def upload_video():
                if "[IP_ADDRESS]" in config.EVENTS_ENDPOINT:
                    return
                upload_session = requests.Session()  # Fresh session — thread-safe
                try:
                    with open(snapshot_path, "rb") as f:
                        file_bytes = f.read()
                    filename = snapshot_path.split("/")[-1]
                    if "\\" in filename:
                        filename = filename.split("\\")[-1]
                    mime = "video/mp4" if filename.lower().endswith('.mp4') else (
                           "video/avi" if filename.lower().endswith('.avi') else "image/jpeg")
                    files = {"snapshot": (filename, file_bytes, mime)}
                    headers = {"X-API-KEY": config.API_KEY}
                    res = upload_session.post(
                        config.EVENTS_ENDPOINT,
                        data={k: str(v) for k, v in payload.items()},
                        files=files,
                        headers=headers,
                        timeout=(15, 120)   # 15s connect, 120s transfer over WiFi
                    )
                    if res.status_code in (200, 201):
                        logger.info(f"[Upload OK] Video attached: {filename}")
                    else:
                        logger.warning(f"[Upload] Backend returned {res.status_code} for {filename}")
                except Exception as e:
                    logger.error(f"[Upload] Failed to attach video {snapshot_path}: {e}")
                finally:
                    upload_session.close()
            
            threading.Thread(target=upload_video, daemon=True).start()


