"""
person_detector.py
Uses an OpenCV DNN MobileNet-SSD to reliably detect persons on a Raspberry Pi.
Fails gracefully if the model files are not present.
"""
import cv2
import os
import logging
import numpy as np

import config

logger = logging.getLogger(__name__)

class PersonDetector:
    def __init__(self):
        self.net = None
        self.classes = ["background", "aeroplane", "bicycle", "bird", "boat",
                        "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
                        "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
                        "sofa", "train", "tvmonitor"]
        self.available = False
        self._load_model()
        
    def _load_model(self):
        if not os.path.exists(config.DNN_PROTOTXT) or not os.path.exists(config.DNN_MODEL):
            logger.warning("MobileNetSSD model files not found in models/. Person detection will strictly fallback to general motion.")
            return
            
        try:
            self.net = cv2.dnn.readNetFromCaffe(config.DNN_PROTOTXT, config.DNN_MODEL)
            # Optimize for Pi CPU if possible
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_DEFAULT)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self.available = True
            logger.info("OpenCV DNN MobileNet-SSD loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load MobileNetSSD via OpenCV: {e}")
            self.available = False

    def detect(self, frame_bgr, confidence_threshold=0.5):
        """
        Detects persons in the frame.
        Returns a list of dicts: [{"bbox": (x, y, w, h), "confidence": float, "centroid": (cx, cy)}]
        """
        detections_list = []
        if not self.available or frame_bgr is None:
            return detections_list
            
        (h, w) = frame_bgr.shape[:2]
        
        try:
            # Prepare blob 300x300 for MobileNet SSD
            blob = cv2.dnn.blobFromImage(cv2.resize(frame_bgr, (300, 300)), 
                                         0.007843, (300, 300), 127.5)
            self.net.setInput(blob)
            detections = self.net.forward()
            
            for i in np.arange(0, detections.shape[2]):
                confidence = float(detections[0, 0, i, 2])
                
                if confidence > confidence_threshold:
                    idx = int(detections[0, 0, i, 1])
                    
                    if self.classes[idx] == "person":
                        box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                        (startX, startY, endX, endY) = box.astype("int")
                        
                        # Clamp to frame edges
                        startX = max(0, startX)
                        startY = max(0, startY)
                        endX = min(w - 1, endX)
                        endY = min(h - 1, endY)
                        
                        width = endX - startX
                        height = endY - startY
                        cx = startX + (width // 2)
                        cy = startY + (height // 2)
                        
                        if width > 0 and height > 0:
                            detections_list.append({
                                "bbox": (startX, startY, width, height),
                                "confidence": confidence,
                                "centroid": (cx, cy)
                            })
                            
        except Exception as e:
            logger.error(f"Error during DNN inference: {e}")
            
        return detections_list
