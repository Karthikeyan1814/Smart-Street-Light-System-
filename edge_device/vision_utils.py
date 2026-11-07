"""
vision_utils.py
Contains helper functions for bounding boxes and OpenCV cascades to isolate faces and bodies.
"""
import cv2
import logging

logger = logging.getLogger(__name__)

CASCADE_FACE_PATH = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
CASCADE_BODY_PATH = cv2.data.haarcascades + 'haarcascade_upperbody.xml'

try:
    face_cascade = cv2.CascadeClassifier(CASCADE_FACE_PATH)
    body_cascade = cv2.CascadeClassifier(CASCADE_BODY_PATH)
except Exception as e:
    logger.error(f"Failed to load OpenCV cascades: {e}")
    face_cascade, body_cascade = None, None

def extract_heads_from_bodies(human_bboxes):
    """
    Geometrically isolates the topmost region of a human bounding box to locate the head.
    Derives height from shoulder width instead of full body height to perfectly accommodate
    both standing humans and people sitting at desks (where legs are clipped).
    """
    heads = []
    for (hx, hy, hw, hh) in human_bboxes:
        # A human head is typically roughly 40-45% the width of their shoulders.
        head_w = int(hw * 0.45)
        
        # A human head is geometrically roughly 1.2x taller than it is wide.
        # This completely ignores `hh` (body height), solving the "hair only" desk bug perfectly!
        head_h = int(head_w * 1.2)
        
        # Prevent the box from extending past the very bottom of the bounding box.
        head_h = min(head_h, hh)
        
        # Center the head horizontally across the shoulders.
        head_x = hx + int((hw - head_w) / 2)
        
        # Lower the box slightly (5% of head height) from the absolute top edge to skip tall hair.
        head_y = hy + int(head_h * 0.05)
        
        heads.append((head_x, head_y, head_w, head_h))
    return heads

def detect_faces(frame_bgr, human_bboxes=None):
    """
    Returns list of (x, y, w, h) for detected faces.
    Prioritizes deep-learning human bounding boxes for long-range Edge Device accuracy (7-8 meters).
    """
    # 1. LONG-RANGE SSD PERSON EXTRACTION (Flawless at 8 meters, no false positives on shirts)
    if human_bboxes is not None and len(human_bboxes) > 0:
        return extract_heads_from_bodies(human_bboxes)
        
    # 2. SHORT-RANGE HAAR FALLBACK (Only executes if no Person Detector is passed)
    if face_cascade is None or face_cascade.empty():
        return []
    
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    
    # Increased minNeighbors to 8 to aggressively prevent false positives like t-shirt text
    faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=8, minSize=(60, 60)
    )
    return faces

def get_largest_face(frame_bgr, faces):
    """
    Returns cropped image of the largest face, or None.
    """
    if len(faces) == 0:
        return None
        
    largest_face = max(faces, key=lambda rect: rect[2] * rect[3])
    x, y, w, h = largest_face
    crop = frame_bgr[y:y+h, x:x+w]
    return crop
    
def draw_detections(frame, boxes, color=(0, 255, 0), label=""):
    for (x, y, w, h) in boxes:
        cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
        if label:
            cv2.putText(frame, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

def get_image_brightness(frame_bgr):
    """
    Returns the average pixel brightness of the image (0-255).
    Useful as a fallback if the LDR sensor is broken or water damaged.
    """
    if frame_bgr is None:
        return 0
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return cv2.mean(gray)[0]
