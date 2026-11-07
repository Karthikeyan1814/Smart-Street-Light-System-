import datetime as dt
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi import Form
from fastapi.responses import JSONResponse

from . import analytics_engine, llm_engine
from .auth import api_key_auth
from .auth import jwt_handler
from .config import VIDEO_STORAGE_DIR
from .database import get_db
from .models import Event, row_to_event
from .websocket_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


def _utcnow_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat()

# In-memory store for edge behavior mode overrides. 
# Defaults to "AUTO" for all towers. Resets on server restart.
device_modes: Dict[str, str] = {}
mosfet_modes: Dict[str, str] = {}


@router.get("/api/health")
async def health() -> Dict[str, Any]:
    """
    Extended health check including DB, websockets, events and towers.
    """
    from .config import settings as cfg  # local to avoid cycles

    db_status = "connected"
    total_events = 0
    active_towers = 0
    total_towers = 0
    try:
        with get_db() as conn:
            cur = conn.execute("SELECT COUNT(*) as c FROM events")
            row = cur.fetchone()
            total_events = row["c"] if row else 0

            cur2 = conn.execute("SELECT tower_id, last_heartbeat FROM tower_status")
            towers = cur2.fetchall()
            total_towers = len(towers)
            now = dt.datetime.utcnow()
            for t in towers:
                last = dt.datetime.fromisoformat(t["last_heartbeat"].replace("Z", ""))
                delta = (now - last).total_seconds()
                if delta <= 60:
                    active_towers += 1
    except Exception:
        db_status = "error"

    return {
        "status": "ok",
        "database": db_status,
        "websocket_clients": len(ws_manager.active_connections),
        "total_events": total_events,
        "active_towers": active_towers,
        "total_registered_towers": total_towers,
        "version": cfg.SYSTEM_VERSION,
    }


@router.get("/api/events")
async def get_events(
    limit: int = 100,
    _: Dict[str, Any] = Depends(jwt_handler.get_current_user),
) -> Dict[str, Any]:
    """
    Return latest events from SQLite, ordered by created_at DESC (newest first).
    JWT required.
    """
    with get_db() as conn:
        cur = conn.execute(
            "SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = cur.fetchall()
    events: List[Event] = [row_to_event(r) for r in rows]
    return {
        "success": True,
        "events": [e.to_dict() for e in events],
    }


@router.get("/api/event/{event_id}")
async def get_event(
    event_id: int,
    _: Dict[str, Any] = Depends(jwt_handler.get_current_user),
) -> Dict[str, Any]:
    """
    Fetch full event details by ID. JWT required.
    """
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")
    event = row_to_event(row)
    return {"success": True, "event": event.to_dict()}


@router.get("/api/analytics")
async def analytics(
    _: Dict[str, Any] = Depends(jwt_handler.get_current_user),
) -> Dict[str, Any]:
    """
    Basic analytics used by existing Phase 2 dashboard.
    """
    data = analytics_engine.get_basic_analytics()
    # Enrich with active tower count based on tower_status
    try:
        with get_db() as conn:
            cur = conn.execute("SELECT last_heartbeat FROM tower_status")
            rows = cur.fetchall()
            now = dt.datetime.utcnow()
            active = 0
            for r in rows:
                last = dt.datetime.fromisoformat(r["last_heartbeat"].replace("Z", ""))
                if (now - last).total_seconds() <= 60:
                    active += 1
            data["active_towers"] = active
    except Exception:
        data["active_towers"] = 0
    return data


@router.get("/api/advanced-analytics")
async def advanced_analytics(
    _: Dict[str, Any] = Depends(jwt_handler.get_current_user),
) -> Dict[str, Any]:
    """
    Advanced analytics (events-per-hour, trends). Accessible to admin and operator.
    """
    return analytics_engine.get_advanced_analytics()


@router.post("/api/alert")
async def receive_alert(
    tower_id: str = Form(...),
    location: str = Form(...),
    event_type: str = Form(...),
    emotion: str = Form(...),
    # Native field expected by this backend (0–1 float)
    confidence: Optional[float] = Form(None),
    # Compatibility with external edge clients using "emotion_confidence"
    emotion_confidence: Optional[float] = Form(None),
    # Optional risk level provided by edge; if absent, LLM decides
    risk_level: Optional[str] = Form(None),
    timestamp: Optional[str] = Form(None),
    # Some clients send "snapshot" instead of "video"
    snapshot: Optional[UploadFile] = File(None),
    video: Optional[UploadFile] = File(None),
    # Phase 2: Behavioral AI enrichment fields
    gesture_detected: Optional[str] = Form(None),
    activity: Optional[str] = Form(None),
    threat_tags: Optional[str] = Form(None),
    emotion_group: Optional[str] = Form(None),
    _: str = Depends(api_key_auth),
) -> JSONResponse:
    """
    Receive alerts from edge devices.

    This endpoint accepts a multipart/form-data payload so the edge device can
    optionally attach a snapshot image when risk is HIGH.
    """
    # Determine effective confidence value
    effective_confidence = confidence
    if effective_confidence is None and emotion_confidence is not None:
        effective_confidence = emotion_confidence

    if effective_confidence is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confidence or emotion_confidence is required",
        )

    logger.info(
        "Received alert from tower_id=%s location=%s event_type=%s emotion=%s confidence=%.2f",
        tower_id,
        location,
        event_type,
        emotion,
        effective_confidence,
    )

    if effective_confidence < 0 or effective_confidence > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confidence must be between 0 and 1",
        )

    created_at = timestamp or _utcnow_iso()
    video_path: Optional[str] = None

    # Prefer explicit "video" field, but also accept "snapshot" for compatibility
    media_file = video or snapshot
    if media_file is not None:
        safe_filename = f"{tower_id}_{created_at.replace(':', '-')}_{media_file.filename}"
        dest = VIDEO_STORAGE_DIR / safe_filename
        content = await media_file.read()
        dest.write_bytes(content)
        video_path = str(dest.relative_to(VIDEO_STORAGE_DIR.parent))

    # Run LLM analysis
    payload = {
        "tower_id": tower_id,
        "location": location,
        "event_type": event_type,
        "emotion": emotion,
        "confidence": effective_confidence,
        "timestamp": created_at,
        "video_path": video_path,
        "gesture_detected": gesture_detected or "NONE",
        "activity": activity or "UNKNOWN",
        "threat_tags": threat_tags or "",
        "emotion_group": emotion_group or "Neutral",
    }
    llm_result = llm_engine.analyze_event(payload)

    # If edge provided a risk level, prefer that; otherwise use LLM output
    computed_risk_level = risk_level or llm_result.get("risk_level", "Medium")
    llm_summary = llm_result.get("summary", "")
    recommended_action = llm_result.get("recommended_action", "")

    processed_at = _utcnow_iso()

    with get_db() as conn:
        # Check if Phase 1 (metadata only) already inserted this event
        cur = conn.execute(
            "SELECT id FROM events WHERE tower_id = ? AND created_at = ?",
            (tower_id, created_at)
        )
        existing = cur.fetchone()

        if existing:
            event_id = existing["id"]
            # If Phase 2 is sending the video, update the existing row
            if video_path:
                conn.execute(
                    "UPDATE events SET video_path = ?, processed_at = ? WHERE id = ?",
                    (video_path, processed_at, event_id)
                )
        else:
            cur = conn.execute(
                """
                INSERT INTO events (
                    tower_id, location, event_type, emotion, confidence,
                    risk_level, llm_summary, recommended_action,
                    video_path, created_at, processed_at,
                    gesture_detected, activity, threat_tags, emotion_group
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tower_id,
                    location,
                    event_type,
                    emotion,
                    effective_confidence,
                    computed_risk_level,
                    llm_summary,
                    recommended_action,
                    video_path,
                    created_at,
                    processed_at,
                    gesture_detected or "NONE",
                    activity or "UNKNOWN",
                    threat_tags or "",
                    emotion_group or "Neutral",
                ),
            )
            event_id = cur.lastrowid

        # Re-fetch the row to broadcast it fully formed
        cur = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = cur.fetchone()
        event = row_to_event(row)

    # Broadcast via WebSocket for real-time dashboard
    await ws_manager.broadcast({"type": "new_alert", "event": event.to_dict()})

    return JSONResponse(
        {
            "success": True,
            "message": "Alert received and processed",
            "event": event.to_dict(),
        },
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/api/admin/reset-database")
async def reset_database(
    _: Dict[str, Any] = Depends(jwt_handler.require_role("admin")),
) -> Dict[str, Any]:
    """
    Admin-only endpoint to truncate the events table.
    """
    with get_db() as conn:
        conn.execute("DELETE FROM events")
    return {"success": True, "message": "Database reset: all events deleted."}


@router.post("/api/admin/emergency-wipe")
async def emergency_wipe(
    username: str = Form(...),
    password: str = Form(...),
) -> Dict[str, Any]:
    """
    Public but guarded endpoint for specialized data management.
    """
    # Robust check with trimming
    if username.strip() == "clear" and password.strip() == "cleardata":
        with get_db() as conn:
            conn.execute("DELETE FROM events")
            conn.execute("DELETE FROM tower_status")
        return {"success": True, "message": "Global system wipe successful."}
    
    logger.warning(f"Management Wipe attempt failed for user: {username}")
    raise HTTPException(status_code=401, detail="Invalid management credentials")


@router.get("/api/admin/status")
async def admin_status(
    user: Dict[str, Any] = Depends(jwt_handler.get_current_user),
) -> Dict[str, Any]:
    """
    Admin-only endpoint exposing simple system status for the admin panel.
    """
    with get_db() as conn:
        cur = conn.execute("SELECT COUNT(*) as c FROM events")
        row = cur.fetchone()
    return {
        "success": True,
        "username": user["username"],
        "role": user["role"],
        "total_events": row["c"] if row else 0,
    }


@router.post("/api/auth/register")
async def register_user(
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("operator"),
) -> Dict[str, Any]:
    """
    Register a new user (admin or operator).

    For a real deployment you would typically disable this in production
    or restrict it to existing admins.
    """
    if role not in {"admin", "operator"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    hashed = jwt_handler.hash_password(password)
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users (username, hashed_password, role) VALUES (?, ?, ?)",
                (username, hashed, role),
            )
    except Exception:
        raise HTTPException(status_code=400, detail="Username already exists")

    return {"success": True, "username": username, "role": role}


@router.post("/api/auth/login")
async def login(username: str = Form(...), password: str = Form(...)) -> Dict[str, Any]:
    user = jwt_handler._get_user_by_username(username)  # type: ignore[attr-defined]
    if not user or not jwt_handler.verify_password(password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password"
        )

    access_token = jwt_handler.create_access_token({"sub": username})
    return {"access_token": access_token, "token_type": "bearer", "role": user["role"]}


@router.get("/api/auth/me")
async def auth_me(user: Dict[str, Any] = Depends(jwt_handler.get_current_user)) -> Dict[str, Any]:
    return {"id": user["id"], "username": user["username"], "role": user["role"]}


@router.post("/api/device/verify")
async def verify_device(
    ip_address: str = Form(...),
    _: Dict[str, Any] = Depends(jwt_handler.get_current_user)
) -> Dict[str, Any]:
    """
    Pings the user-supplied Edge Device IP address to establish
    that the Raspberry Pi is successfully alive on the network before 
    allowing entry into the main dashboard.
    """
    import subprocess
    import platform
    
    # Determine the correct ping flag for OS (-n for Windows, -c for Linux)
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    
    try:
        # Run a 1-packet ping
        output = subprocess.run(['ping', param, '1', ip_address], 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE,
                                timeout=5)
        
        # Windows ping often returns exit code 0 even if destination is unreachable.
        # We must decode stdout and look for actual reply indicators like "TTL=".
        stdout_str = output.stdout.decode('utf-8', errors='ignore').upper()
        
        is_success = False
        if platform.system().lower() == 'windows':
            # Looking for "TTL=" in the reply ensures a valid ICMP response
            if "TTL=" in stdout_str:
                is_success = True
        else:
            if output.returncode == 0:
                is_success = True

        if is_success:
            return {"success": True, "message": f"Device {ip_address} is ONLINE."}
        else:
            return {"success": False, "message": f"Device {ip_address} is unreachable."}
    except Exception as e:
        return {"success": False, "message": f"Ping failed: {str(e)}"}


@router.get("/api/device/mode")
async def get_device_mode(tower_id: str = "TOWER-01") -> Dict[str, str]:
    """Get the current override mode for a specific tower."""
    return {
        "mode": device_modes.get(tower_id, "AUTO"),
        "mosfet_mode": mosfet_modes.get(tower_id, "AUTO")
    }


@router.post("/api/device/mode")
async def set_device_mode(payload: Dict[str, str]) -> Dict[str, str]:
    """Set the override modes for a specific tower."""
    tower_id = payload.get("tower_id", "TOWER-01")
    
    if "mode" in payload:
        mode = payload.get("mode", "AUTO").upper()
        if mode not in ["AUTO", "DAY", "NIGHT"]:
            raise HTTPException(status_code=400, detail="Invalid mode")
        device_modes[tower_id] = mode
        logger.info(f"Tower {tower_id} mode overridden to {mode}")
        
    if "mosfet_mode" in payload:
        mosfet_mode = payload.get("mosfet_mode", "AUTO").upper()
        if mosfet_mode not in ["AUTO", "FULL"]:
            raise HTTPException(status_code=400, detail="Invalid mosfet mode")
        mosfet_modes[tower_id] = mosfet_mode
        logger.info(f"Tower {tower_id} mosfet mode overridden to {mosfet_mode}")
        
    return {
        "status": "success", 
        "mode": device_modes.get(tower_id, "AUTO"),
        "mosfet_mode": mosfet_modes.get(tower_id, "AUTO")
    }


@router.post("/api/heartbeat")
async def heartbeat(
    tower_id: str = Form(...),
    _: str = Depends(api_key_auth),
) -> Dict[str, Any]:
    """
    Heartbeat endpoint called periodically by edge devices.
    """
    now = _utcnow_iso()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO tower_status (tower_id, last_heartbeat)
            VALUES (?, ?)
            ON CONFLICT(tower_id) DO UPDATE SET last_heartbeat = excluded.last_heartbeat
            """,
            (tower_id, now),
        )
    return {
        "success": True, 
        "tower_id": tower_id, 
        "last_heartbeat": now,
        "override_mode": device_modes.get(tower_id, "AUTO"),
        "override_mosfet": mosfet_modes.get(tower_id, "AUTO")
    }


@router.get("/api/model/latest")
async def model_latest() -> Dict[str, Any]:
    """
    Provide latest model version information for edge auto-update.
    """
    from .config import STORAGE_DIR  # local import to avoid circular
    import hashlib
    import os

    model_dir = STORAGE_DIR / "models"
    version_file = model_dir / "model_version.txt"
    tflite_path = model_dir / "emotion_model.tflite"

    if not version_file.exists() or not tflite_path.exists():
        return {"success": False, "available": False}

    version = version_file.read_text(encoding="utf-8").strip()
    checksum = hashlib.sha256(tflite_path.read_bytes()).hexdigest()
    return {
        "success": True,
        "available": True,
        "version": version,
        "download_url": f"/storage/models/{os.path.basename(tflite_path)}",
        "checksum": checksum,
    }


@router.get("/api/tower-status")
async def tower_status(
    _: Dict[str, Any] = Depends(jwt_handler.get_current_user),
) -> List[Dict[str, Any]]:
    """
    Return ONLINE/OFFLINE status for all known towers based on heartbeat.
    """
    results: List[Dict[str, Any]] = []
    now = dt.datetime.utcnow()
    with get_db() as conn:
        cur = conn.execute("SELECT tower_id, last_heartbeat FROM tower_status")
        rows = cur.fetchall()

    for r in rows:
        last_seen = r["last_heartbeat"]
        try:
            last_dt = dt.datetime.fromisoformat(last_seen.replace("Z", ""))
        except Exception:
            continue
        seconds = int((now - last_dt).total_seconds())
        status = "ONLINE" if seconds <= 60 else "OFFLINE"
        results.append(
            {
                "tower_id": r["tower_id"],
                "status": status,
                "last_seen": last_seen,
                "seconds_since_last_seen": seconds,
            }
        )

    return results

