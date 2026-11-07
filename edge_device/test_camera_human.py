import cv2
import time
import threading
import logging
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

from camera_manager import CameraManager
from person_detector import PersonDetector
from person_tracker import CentroidTracker
from vision_utils import detect_faces
from emotion_model import EmotionPredictor

logging.basicConfig(level=logging.INFO)

# Global variables to safely share the most recent frame
latest_frame = None
lock = threading.Lock()

class CamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.endswith('.mjpg'):
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--jpgboundary')
            self.end_headers()
            
            while True:
                try:
                    with lock:
                        frame_to_encode = latest_frame.copy() if latest_frame is not None else None
                        
                    if frame_to_encode is not None:
                        ret, jpg = cv2.imencode('.jpg', frame_to_encode, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
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
            self.end_headers()
            html = b"""
            <html>
                <head><title>Edge Device - Debug Emotion ROI</title></head>
                <body style="background-color: #222; color: #fff; text-align: center; font-family: sans-serif;">
                    <h1>Live Camera: Debugging Emotion Input</h1>
                    <p style="color: #aaa;">Look at the top-left corner of the video. It shows Exactly what the AI sees as your face!</p>
                    <img src='/stream.mjpg' style="max-width: 100%; border: 3px solid #555;"/>
                </body>
            </html>
            """
            self.wfile.write(html)

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread to prevent blocking."""

def capture_loop():
    global latest_frame
    
    print("[Thread] Initializing CameraManager...")
    cam = CameraManager()
    cam.start()
    
    print("[Thread] Loading PersonDetector & Action Tracker...")
    person_detector = PersonDetector()
    tracker = CentroidTracker()

    print("[Thread] Loading EmotionPredictor...")
    emotion_model = EmotionPredictor()
    
    print("=" * 60)
    print(f">>> CRITICAL AI MODE CHECK: The emotion model loaded using '{emotion_model.mode.upper()}' engine! <<<")
    if emotion_model.mode == "heuristic":
        print("    WARNING: 'HEURISTIC' mode means the AI model FAILED TO LOAD entirely!")
        print("    It is returning a hardcoded 'Neutral' 40% every single time. Check your model files.")
    print("=" * 60)

    time.sleep(2.0)

    try:
        while True:
            frame = cam.get_frame()
            if frame is not None:
                # 1. PERSON DETECTION & CONTINUOUS ACTION TRACKING
                person_detections = person_detector.detect(frame, confidence_threshold=0.5)
                tracked_objects = tracker.update(person_detections)
                
                human_bboxes = []
                for det in person_detections:
                    x, y, w, h = det['bbox']
                    human_bboxes.append((x, y, w, h))
                    
                # VITAL NEW FEATURE: VISUALIZING ACTIONS ON THE DEBUGGER
                for obj_id, person in tracked_objects.items():
                    px, py, pw, ph = person.bbox
                    
                    loiter_time = person.loitering_time()
                    action_text = f"[ID:{obj_id}] {person.speed_label.upper()} {person.direction.upper()}"
                    
                    if loiter_time > 2.0:
                        action_text += f" | WAIT:{loiter_time:.1f}s"
                        
                    # Dynamic Color Coding based on Threat Level
                    box_color = (0, 255, 0) # Green = Walking
                    if person.speed_label == "fast":
                        box_color = (0, 0, 255) # Red = Running / High Speed
                        # Console Output for Action Debugging
                        print(f"[ACTION DETECTED] Target {obj_id} is SPRINTING {person.direction}!")
                    elif loiter_time > 5.0:
                        box_color = (0, 255, 255) # Yellow = Suspicious Loitering
                        # Console Output for Action Debugging
                        if int(loiter_time*10) % 20 == 0: 
                            print(f"[ACTION DETECTED] Target {obj_id} is LOITERING for {loiter_time:.1f}s")
                            
                    cv2.rectangle(frame, (px, py), (px + pw, py + ph), box_color, 2)
                    cv2.putText(frame, action_text, (px, py - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)

                # 2. LONG-RANGE FACE DETECTION
                # By passing the SSD Person Tracker boxes, we geometrically guarantee Face location
                # without using the Haar Cascades (which mistakenly read letters on your shirt).
                using_fallback = (len(human_bboxes) > 0)
                faces = list(detect_faces(frame, human_bboxes=human_bboxes))
                
                # Track the first face ROI to display in the corner of the stream
                corner_debug_roi = None

                # Evaluate all specific face regions
                for (fx, fy, fw, fh) in faces:
                    roi_y1, roi_y2 = max(0, fy), min(frame.shape[0], fy+fh)
                    roi_x1, roi_x2 = max(0, fx), min(frame.shape[1], fx+fw)
                    face_roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
                    
                    if face_roi.size > 0 and face_roi.shape[0] > 10 and face_roi.shape[1] > 10:
                        
                        # Save the first face for debugging
                        if corner_debug_roi is None:
                            corner_debug_roi = face_roi.copy()
                            
                        # Predict the exact Emotion based on the cropped ROI
                        emotion_label, emo_conf = emotion_model.predict(face_roi)
                        
                        box_color = (255, 0, 0) if not using_fallback else (255, 0, 255) # Pink if fallback
                        cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), box_color, 2)
                        
                        emo_text = f"{emotion_label} ({emo_conf*100:.0f}%)"
                        if emotion_label in ["Angry", "Fear", "Sad"]: text_color = (0, 0, 255)
                        elif emotion_label == "Happy": text_color = (0, 255, 255)
                        else: text_color = (255, 150, 0)
                            
                        cv2.putText(frame, emo_text, (fx, max(15, fy - 10)), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)

                # 3. DRAW ROI DEBUG WINDOW
                if corner_debug_roi is not None:
                    try:
                        # Resize it big enough to see
                        db_size = 120
                        debug_resized = cv2.resize(corner_debug_roi, (db_size, db_size))
                        
                        # Add a grey border
                        debug_resized = cv2.copyMakeBorder(debug_resized, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(100,100,100))
                        bh, bw = debug_resized.shape[:2]
                        
                        # Overlay it on top left
                        frame[10:10+bh, 10:10+bw] = debug_resized
                        
                        # Title
                        title = "Real Face" if not using_fallback else "Estimated Fallback Face"
                        cv2.putText(frame, "AI VISION ROI:", (10, bh + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                        if emotion_model.mode == "heuristic":
                            cv2.putText(frame, "ERROR: MODEL MISSING", (10, bh + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
                            
                    except Exception as e:
                        pass # Ignore resize errors

                with lock:
                    latest_frame = frame
                    
                # CPU STARVATION FIX: 
                # Without this sleep, the AI Loop tries to run at 30+ FPS, maxing out the Pi CPU at 100%.
                # When you open the web browser, the video encoder starves for CPU, freezing the camera.
                # Yielding here allows the HTTP server and libcamera to run smoothly without hangs!
                time.sleep(0.15) 
            else:
                time.sleep(0.5)
    finally:
        cam.stop()

def main():
    print("Starting video capture with EMOTION DEBUGGING...")
    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()
    
    port = 8080
    print("=" * 60)
    print(f"WEB SERVER RUNNING!")
    print(f"->  http://<YOUR_PI_IP_ADDRESS>:{port}/")
    print("=" * 60)
    
    try:
        server = ThreadedHTTPServer(('0.0.0.0', port), CamHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
        server.socket.close()

if __name__ == '__main__':
    main()
