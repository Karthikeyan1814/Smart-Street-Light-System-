"""
edge_main.py
Main entry point for the Smart Street Lighting Edge Device.
Initializes hardware, models, camera, and runs the continuous monitoring loop.
"""
import time
import logging
import sys
import os

# Suppress libcamera C++ bindings from flooding stdout with PDAF format warnings (Raspi OS bug)
os.environ["LIBCAMERA_LOG_LEVELS"] = "FATAL"

# Ensure clean logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "edge.log"))
    ]
)
logger = logging.getLogger(__name__)

import config
from hardware_controller import HardwareController
from camera_manager import CameraManager
from emotion_model import EmotionPredictor
from vision_utils import detect_faces, get_largest_face, get_image_brightness
from motion_analyzer import MotionAnalyzer
from person_detector import PersonDetector
from person_tracker import CentroidTracker
from decision_engine import DecisionEngine
from alert_sender import AlertSender
from snapshot_manager import SnapshotManager
from metrics import get_system_metrics
from gesture_detector import GestureDetector
from behavior_analyzer import BehaviorAnalyzer

import cv2
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

# Global variables for HTTP Livestream
latest_frame = None
frame_lock = threading.Lock()

class CamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.endswith('.mjpg'):
            # --- Auto-Discovery Feature --- 
            # Dynamically lock onto whatever IP address opened the dashboard stream!
            client_ip = self.client_address[0]
            if f"http://{client_ip}:5000/api" != config.HUB_URL_BASE:
                logger.info(f"==> [Auto-Discovery] Dashboard detected at {client_ip}! Re-routing all backend AI alerts dynamically.")
                config.HUB_URL_BASE = f"http://{client_ip}:5000/api"
                config.EVENTS_ENDPOINT = f"{config.HUB_URL_BASE}/alert"
                config.HEARTBEAT_ENDPOINT = f"{config.HUB_URL_BASE}/heartbeat"
                
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--jpgboundary')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            while True:
                try:
                    with frame_lock:
                        frame_to_encode = latest_frame.copy() if latest_frame is not None else None
                        
                    if frame_to_encode is not None:
                        ret, jpg = cv2.imencode('.jpg', frame_to_encode, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
                        if ret:
                            self.wfile.write(b'--jpgboundary\r\n')
                            self.send_header('Content-type', 'image/jpeg')
                            self.send_header('Content-length', str(jpg.size))
                            self.end_headers()
                            self.wfile.write(jpg.tobytes())
                            self.wfile.write(b'\r\n')
                    
                    time.sleep(0.08)
                except Exception as e:
                    break
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            html = b"""
            <html>
                <head><title>Edge Live Stream (Production)</title></head>
                <body style="background-color: #111; color: #fff; text-align: center; font-family: sans-serif; padding-top: 50px;">
                    <h1 style="color: #00f0ff;">Node Diagnostics Feed</h1>
                    <p style="color: #aaa;">This is the raw Edge pipeline output with real-time AI visual overlays.</p>
                    <img src='/stream.mjpg' style="max-width: 90%; border: 2px solid #333; border-radius: 8px;"/>
                </body>
            </html>
            """
            self.wfile.write(html)

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass


def main():
    logger.info("==================================================================")
    logger.info(" Emotion-Aware Smart Street Lighting - Edge Device (Production)   ")
    logger.info(f" Tower ID: {config.TOWER_ID} | Location: {config.LOCATION}")
    logger.info("==================================================================")
    
    # 1. Initialize Subsystems
    logger.info("[Step] Checking model files...")
    logger.info(f"[Model] emotion.tflite present: {os.path.exists(config.TFLITE_MODEL_PATH)}")
    logger.info(f"[Model] emotion_detection_model.h5 present: {getattr(config, 'KERAS_MODEL_PATH', False) and os.path.exists(config.KERAS_MODEL_PATH)}")
    logger.info(f"[Model] MobileNetSSD present: {os.path.exists(config.DNN_PROTOTXT)}")
    
    hw = HardwareController()
    cam = CameraManager()
    model = EmotionPredictor()
    motion = MotionAnalyzer()
    
    detector = PersonDetector()
    tracker = CentroidTracker()
    gesture_det = GestureDetector()
    behavior = BehaviorAnalyzer()
    
    decision = DecisionEngine(hw)
    alerts = AlertSender()
    snapshots = SnapshotManager()
    
    # 2. Start Camera & Stream Server
    cam.start()
    
    server_port = 8080
    http_server = ThreadedHTTPServer(('0.0.0.0', server_port), CamHandler)
    server_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    server_thread.start()
    logger.info(f"Live Cam Server running on port {server_port}")
    
    # Let sensor stabilize
    time.sleep(2)
    
    last_heartbeat = time.time()
    ALERT_COOLDOWN_SEC    = 30.0  # Minimum seconds between normal alerts
    CRITICAL_COOLDOWN_SEC = 20.0  # Minimum seconds between Critical (X_GESTURE/ACCIDENT) alerts
    HEARTBEAT_INTERVAL   = 60.0  # Heartbeat ping interval
    
    last_alert_time = 0
    
    last_debug_print = 0
    
    try:
        logger.info("Entering Main Monitoring Loop...")
        while True:
            cycle_start = time.time()
            
            # --- Per-frame Capture ---
            frame = cam.get_frame()
            if frame is None:
                logger.warning("[Camera] Failed to read frame.")
                time.sleep(1)
                continue
                
            # Dual-Sense Validation Brightness
            frame_brity = get_image_brightness(frame)
                
            # --- Vision Processing ---
            # 1. Base Motion
            motion_data = motion.analyze(frame)
            mot_detected, mot_speed, mot_dir, mot_x, blob_count = motion_data
            
            # 2. Maintain 20-second rolling buffer
            snapshots.register_frame(frame)
            
            # 2. DNN Person Detection & Tracking
            person_detections = detector.detect(frame)
            tracked_objects = tracker.update(person_detections)
            primary_target = tracker.get_primary_target()
            
            # 3. Face / Emotion (Long-Range Multi-Face Aggregation via SSD Tracking)
            # The Edge Device will operate from 7-8 meters high! Haar Cascades will mathematically fail.
            # We strictly extract human head coordinates from the Deep Learning Person Tracker bounding boxes.
            human_bboxes = [det['bbox'] for det in person_detections]
            faces = detect_faces(frame, human_bboxes=human_bboxes)
            
            dominant_emotion = "Neutral"
            top_emo_conf = 0.0
            
            if len(faces) > 0:
                face_emotions = []
                for (fx, fy, fw, fh) in faces:
                    face_roi = frame[fy:fy+fh, fx:fx+fw]
                    em, conf = model.predict(face_roi)
                    face_emotions.append((em, conf))
                    logger.info(f"[Vision] Detected Emotion: {em} (Confidence: {conf*100:.1f}%) [Box: {fw}x{fh}]")
                
                # Priority ranking for the Hub payload
                emotion_priority = {"Angry": 6, "Fear": 5, "Sad": 4, "Surprise": 3, "Disgust": 2, "Happy": 1, "Neutral": 0}
                
                # Sort by priority, then by confidence
                sorted_emotions = sorted(face_emotions, key=lambda x: (emotion_priority.get(x[0], 0), x[1]), reverse=True)
                dominant_emotion, top_emo_conf = sorted_emotions[0]
                
            face_data = (dominant_emotion, top_emo_conf, len(faces))
            pir_motion = hw.is_motion_detected()

            # --- Gesture Detection (on primary target bounding box) ---
            gesture = "NONE"
            if primary_target is not None:
                gesture = gesture_det.detect(frame, primary_target.bbox)

            # --- Behavioral Threat Analysis ---
            behavior_verdict = behavior.evaluate(tracked_objects, dominant_emotion, top_emo_conf, gesture)
            behavior.cleanup_missing(set(tracked_objects.keys()))
            
            # --- Decision Engine ---
            event_type, risk_level, action, new_servo_angle, new_brightness, indicator_on = decision.evaluate(
                motion_data, face_data, tracked_objects, primary_target, frame_brightness=frame_brity, pir_motion=pir_motion
            )

            # Behavior verdict overrides risk_level and event_type when it produces a stronger signal
            from behavior_analyzer import max_threat
            if behavior_verdict["event_type"] and max_threat(behavior_verdict["threat_level"], risk_level) != risk_level:
                risk_level = behavior_verdict["threat_level"]
                event_type = behavior_verdict["event_type"]
            
            # --- Visual Override Integration (from test_camera_human) ---
            # 1. Action Bounding Boxes
            for obj_id, person in tracked_objects.items():
                px, py, pw, ph = person.bbox
                loiter_time = person.loitering_time()
                action_text = f"[ID:{obj_id}] {person.speed_label.upper()} {person.direction.upper()}"
                
                if loiter_time > 2.0:
                    action_text += f" | WAIT:{loiter_time:.1f}s"
                
                box_color = (0, 255, 0) # Green = Walking
                if person.speed_label == "fast":
                    box_color = (0, 0, 255) # Red = Sprinting
                elif loiter_time > config.LOITERING_THRESHOLD_SEC:
                    box_color = (0, 255, 255) # Yellow = Suspicious
                    
                cv2.rectangle(frame, (px, py), (px + pw, py + ph), box_color, 2)
                cv2.putText(frame, action_text, (px, py - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)
            
            # 2. Emotion Text
            if len(faces) > 0:
                for i, (fx, fy, fw, fh) in enumerate(faces):
                    # We correlated face_emotions exactly index-for-index with faces in line 167 loop
                    if i < len(face_emotions):
                        em, conf = face_emotions[i]
                        emo_text = f"{em} ({conf*100:.0f}%)"
                        text_color = (0, 0, 255) if em in ["Angry", "Fear", "Sad"] else (0, 255, 255) if em == "Happy" else (255, 150, 0)
                        cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (255, 0, 0), 2)
                        cv2.putText(frame, emo_text, (fx, max(15, fy - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)
                        
            # Store the heavily visualized frame for the HTTP Livestream
            global latest_frame
            with frame_lock:
                latest_frame = frame.copy()
            
            # --- Execute Actions ---
            hw.set_servo_angle(new_servo_angle)
            hw.set_light_brightness(new_brightness)
            # Removed redundant hw.toggle_relay(2) call to stop IR relay collision clicking
            
            now = time.time()
            
            # --- Hardware Debug Print (Every 5 seconds) ---
            if now - last_debug_print > 5.0:
                logger.info(f"[HARDWARE DEBUG] Mode: {decision.current_mode} | Camera Brightness: {frame_brity:.1f} | LDR Pin: {hw.is_dark()} | Floodlight PWM: {new_brightness}%")
                last_debug_print = now
            
            # --- Event Dispatch ---
            # Critical alerts (X_GESTURE, ACCIDENT) get a shorter cooldown, not a bypass.
            # Bypassing cooldown entirely caused a video storm when gesture was held.
            is_gesture_critical = behavior_verdict.get("threat_level") == "Critical" or risk_level == "Critical"
            if is_gesture_critical:
                cooldown_ok = (now - last_alert_time > CRITICAL_COOLDOWN_SEC)
            else:
                cooldown_ok = (now - last_alert_time > ALERT_COOLDOWN_SEC)

            if event_type and cooldown_ok:
                logger.info(f"*** EVENT TRIGGERED: {event_type} (Risk: {risk_level}) *** Action: {action}")
                
                # Critical or High Risk → always save a full video clip
                is_vid_event = is_gesture_critical or risk_level == "High"
                if is_vid_event:
                    logger.info(f"{'Critical' if is_gesture_critical else 'High'} Risk: Generating emergency video clip...")
                    snap_path = snapshots.save_video(event_prefix=event_type)
                    last_alert_time = now
                else:
                    snap_path = snapshots.save_snapshot(frame, event_prefix=event_type)
                    last_alert_time = now
                
                # Fetch target specific data
                target_x, target_y = -1, -1
                target_speed_lbl = "stationary"
                target_loiter = 0.0
                if primary_target:
                    target_x, target_y = primary_target.centroids[-1]
                    target_speed_lbl = primary_target.speed_label
                    target_loiter = primary_target.loitering_time()
                
                # For gesture events with no face, use 0.95 as the gesture certainty confidence
                effective_conf = top_emo_conf if top_emo_conf and top_emo_conf > 0.0 else (
                    0.95 if gesture == "X_GESTURE" else 0.80
                )

                event_payload = {
                    "event_type": event_type,
                    "risk_level": risk_level,
                    "current_mode": decision.current_mode,
                    "emotion": dominant_emotion,
                    "emotion_confidence": round(effective_conf, 3),
                    # Enriched behavioral fields
                    "gesture_detected": gesture,
                    "activity": behavior_verdict.get("activity", "UNKNOWN"),
                    "threat_tags": ",".join(behavior_verdict.get("threat_tags", [])),
                    "emotion_group": behavior_verdict.get("emotion_group", "Neutral"),
                    # Standard fields
                    "face_detected": len(faces) > 0,
                    "person_detected": len(tracked_objects) > 0,
                    "person_count": len(tracked_objects),
                    "primary_target_detected": primary_target is not None,
                    "target_x": target_x,
                    "target_y": target_y,
                    "motion_detected": mot_detected,
                    "motion_speed_px_s": round(mot_speed * config.FRAMERATE, 2),
                    "motion_speed_label": target_speed_lbl,
                    "movement_direction": primary_target.direction if primary_target else mot_dir,
                    "loitering_seconds": round(target_loiter, 1),
                    "led_brightness": new_brightness,
                    "servo_angle": new_servo_angle,
                    "recommended_action": action
                }
                alerts.send_event(event_payload, snapshot_path=snap_path)
            
            # --- Heartbeat Dispatch ---
            now = time.time()
            if now - last_heartbeat > HEARTBEAT_INTERVAL:
                # Skip heartbeat if auto-discovery hasn't fired yet (URL still has placeholder)
                if "[IP_ADDRESS]" not in config.HEARTBEAT_ENDPOINT:
                    sys_metrics = get_system_metrics()
                    status_dict = {
                        "camera_status": bool(cam.is_running),
                        "pir_status": bool(hw.is_motion_detected()),
                        "ldr_status": bool(hw.is_dark()),
                        **sys_metrics
                    }
                    alerts.send_heartbeat(status_dict)
                last_heartbeat = now

                
            # Maintain roughly fixed framerate loop
            elapsed = time.time() - cycle_start
            sleep_time = max(0.0, (1.0 / config.FRAMERATE) - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("Interrupted by user. Shutting down...")
    except Exception as e:
        logger.critical(f"Fatal error in main loop: {e}", exc_info=True)
    finally:
        cam.stop()
        hw.cleanup()
        logger.info("Shutdown complete.")

if __name__ == "__main__":
    main()
