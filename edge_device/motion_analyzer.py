"""
motion_analyzer.py
Performs frame differencing to detect the bounding box of motion. 
Helps servo track people at night and generate risk scores.
"""
import cv2
import numpy as np

class MotionAnalyzer:
    def __init__(self, min_area=3000):
        self.min_area = min_area
        self.avg_frame = None
        self.last_centroid = None

    def analyze(self, frame_bgr):
        """
        Updates background model and returns motion metadata:
        - detected (bool)
        - speed (float px/frame)
        - direction (str)
        - x_center (int)
        - count (int bounding blobs)
        """
        if frame_bgr is None:
            return False, 0.0, "none", 0, 0
            
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        # Initialize background
        if self.avg_frame is None:
            self.avg_frame = gray.astype("float")
            return False, 0.0, "none", 0, 0

        # Accumulate weighted
        cv2.accumulateWeighted(gray, self.avg_frame, 0.1)
        frame_delta = cv2.absdiff(gray, cv2.convertScaleAbs(self.avg_frame))

        # Threshold and Dilate
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        significant_contours = [c for c in contours if cv2.contourArea(c) > self.min_area]
        blob_count = len(significant_contours)

        if blob_count == 0:
            self.last_centroid = None
            return False, 0.0, "none", 0, 0

        # Find largest motion blob
        largest_contour = max(significant_contours, key=cv2.contourArea)
        (x, y, w, h) = cv2.boundingRect(largest_contour)
        
        current_centroid_x = x + w // 2
        speed = 0.0
        direction = "static"

        if self.last_centroid is not None:
            dx = current_centroid_x - self.last_centroid
            speed = abs(dx)
            if dx > 5:
                direction = "right"
            elif dx < -5:
                direction = "left"
        
        self.last_centroid = current_centroid_x
        
        return True, speed, direction, current_centroid_x, blob_count
