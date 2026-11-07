"""
Emotion detector for the edge device.

This module captures frames using Picamera2 (recommended for Pi Camera Module 3)
and performs very lightweight, rule-based "emotion detection".
"""

import random
from typing import Dict, Any, Tuple, Optional

try:
    import cv2  # type: ignore
except ImportError:
    cv2 = None  # type: ignore

try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None  # type: ignore


def open_camera(camera_index: int = 0):
    """
    Open a camera using Picamera2.

    camera_index kept for compatibility (ignored by Picamera2).
    Returns:
        Picamera2 object or None if unavailable.
    """
    if cv2 is None:
        print("[EmotionDetector] OpenCV not available. Running in simulation mode.")
        return None

    if Picamera2 is None:
        print("[EmotionDetector] Picamera2 not available. Running in simulation mode.")
        return None

    try:
        picam2 = Picamera2()
        config = picam2.create_preview_configuration(
            main={"format": "RGB888", "size": (640, 480)}
        )
        picam2.configure(config)
        picam2.start()
        print("[EmotionDetector] Picamera2 started (640x480 RGB888).")
        return picam2
    except Exception as e:
        print(f"[EmotionDetector] Failed to start Picamera2: {e}. Using simulation mode.")
        return None


def close_camera(camera) -> None:
    """Safely stop Picamera2 camera."""
    try:
        if camera is not None:
            camera.stop()
    except Exception:
        pass


def _simulate_emotion() -> Tuple[str, float]:
    emotions = ["Neutral", "Happiness", "Sadness", "Fear", "Anger"]
    weights = [0.4, 0.25, 0.15, 0.1, 0.1]
    emotion = random.choices(emotions, weights=weights, k=1)[0]
    confidence = round(random.uniform(0.5, 0.95), 2)
    return emotion, confidence


def detect_emotion(
    camera, face_cascade_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Capture a frame from Picamera2 (if available) and perform
    a lightweight face detection + rule-based emotion estimate.
    """
    if camera is None or cv2 is None:
        emotion, confidence = _simulate_emotion()
        return {"emotion": emotion, "confidence": confidence}

    # Load face detector
    if face_cascade_path is None:
        face_cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

    face_cascade = cv2.CascadeClassifier(face_cascade_path)

    # Capture a single frame (RGB from Picamera2)
    try:
        frame_rgb = camera.capture_array()
        if frame_rgb is None:
            raise RuntimeError("capture_array returned None")
    except Exception as e:
        print(f"[EmotionDetector] Failed to capture frame: {e}. Using simulation.")
        emotion, confidence = _simulate_emotion()
        return {"emotion": emotion, "confidence": confidence}

    # Convert RGB -> BGR for OpenCV
    frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)

    if len(faces) == 0:
        emotion = "Neutral"
        confidence = 0.6
    else:
        (x, y, w, h) = max(faces, key=lambda f: f[2] * f[3])
        face_area = w * h

        if face_area > 50000 and len(faces) > 1:
            emotion = "Anger"
            confidence = 0.85
        elif face_area > 40000:
            emotion = "Fear"
            confidence = 0.8
        elif face_area > 25000:
            emotion = "Sadness"
            confidence = 0.75
        else:
            emotion = "Happiness"
            confidence = 0.7

    return {"emotion": emotion, "confidence": round(float(confidence), 2)}
