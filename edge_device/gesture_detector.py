"""
gesture_detector.py  ─  X-Gesture (Crossed Index Fingers) Detector
====================================================================

Reference gesture (from user image):
  • Both hands face the camera at chest height
  • Left index finger points upper-right  (/  slope)
  • Right index finger points upper-left  (\\  slope)
  • Fingers cross in the middle → visible X / diagonal cross shape

Detection algorithm (CPU-only, no ML model):
  1. Crop the FULL person bounding box (gesture is held at chest, not just upper body)
  2. Convert to grayscale → GaussianBlur → Canny edge map
  3. Run HoughLinesP to detect line segments
  4. Classify each line segment into:
       SLASH  ( / ) – angle  30° – 75°  from horizontal
       BSLASH (\\) – angle 105° – 150° from horizontal
  5. If we have at least one SLASH and one BSLASH segment AND their
     midpoints are within the central 60 % of the crop, the finger-X
     pattern is present.
  6. Require 2 consecutive positive frames → fires "X_GESTURE".
     After firing, a 1-second lockout prevents instant re-triggering.
"""

import time
import math
import cv2
import numpy as np


class GestureDetector:
    # Tuning knobs ──────────────────────────────────────────────────
    CONFIRM_FRAMES   = 2      # consecutive positive frames before confirming
    LOCKOUT_SEC      = 30.0   # seconds before the gesture can fire again (prevents storm while pose is held)
    MIN_LINE_LEN     = 25     # minimum pixel length of a Hough segment to count
    CENTER_MARGIN    = 0.20   # midspot must be within this margin of centre x/y
    # ─────────────────────────────────────────────────────────────────

    # Angle windows (in degrees from horizontal, 0° = pointing right)
    _SLASH_MIN,  _SLASH_MAX  = 30, 75    # / direction
    _BSLASH_MIN, _BSLASH_MAX = 105, 150  # \ direction

    def __init__(self):
        self._pos_frames  = 0
        self._last_fire   = 0.0
        self._score_buf   = []    # rolling debug buffer (not used in logic)

    # ─── Public API ──────────────────────────────────────────────────
    def detect(self, frame_bgr: np.ndarray, person_bbox: tuple) -> str:
        """
        Returns "X_GESTURE" when the crossed-index-finger sign is confirmed.
        Returns "NONE" otherwise.

        Args:
            frame_bgr:   Full BGR camera frame
            person_bbox: (x, y, w, h) of the primary tracked person.
                         Pass None to use the full frame.
        """
        if frame_bgr is None:
            self._pos_frames = 0
            return "NONE"

        # Lockout guard – don't re-fire within LOCKOUT_SEC
        if time.time() - self._last_fire < self.LOCKOUT_SEC:
            return "NONE"

        crop = self._get_crop(frame_bgr, person_bbox)
        if crop is None or crop.size == 0:
            self._pos_frames = 0
            return "NONE"

        slash_ok, bslash_ok = self._has_x_lines(crop)

        if slash_ok and bslash_ok:
            self._pos_frames += 1
        else:
            self._pos_frames = 0

        if self._pos_frames >= self.CONFIRM_FRAMES:
            self._pos_frames = 0
            self._last_fire  = time.time()
            return "X_GESTURE"

        return "NONE"

    # ─── Internal helpers ─────────────────────────────────────────────
    def _get_crop(self, frame, bbox):
        """Return the person crop, or the centre-third of the full frame."""
        h_f, w_f = frame.shape[:2]

        if bbox is not None:
            x, y, w, h = bbox
            # Safety clamp
            x = max(0, x)
            y = max(0, y)
            w = min(w, w_f - x)
            h = min(h, h_f - y)
            if w < 20 or h < 20:
                return None
            return frame[y: y + h, x: x + w]
        else:
            # Full frame – use central 50 % strip
            x0 = w_f // 4
            x1 = w_f * 3 // 4
            y0 = h_f // 4
            y1 = h_f * 3 // 4
            return frame[y0:y1, x0:x1]

    def _has_x_lines(self, crop):
        """
        Returns (slash_found, bslash_found).
        Each is True if a qualifying line segment of the respective
        diagonal orientation was found near the crop centre.
        """
        gray  = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blur  = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 40, 120)

        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=20,
            minLineLength=self.MIN_LINE_LEN,
            maxLineGap=10,
        )

        if lines is None:
            return False, False

        h, w = crop.shape[:2]
        cx, cy = w / 2.0, h / 2.0
        margin_x = w * self.CENTER_MARGIN * 2   # acceptable x distance from centre
        margin_y = h * self.CENTER_MARGIN * 2

        slash_found  = False
        bslash_found = False

        for seg in lines:
            x1, y1, x2, y2 = seg[0]

            # Angle from horizontal (0-180°, always positive)
            angle = math.degrees(math.atan2(abs(y2 - y1), abs(x2 - x1)))
            # We need the signed slope direction:
            #   dy negative while dx positive → going up-right  → SLASH  /
            #   dy positive while dx positive → going down-right → BSLASH \
            dx = x2 - x1
            dy = y2 - y1

            # Midpoint of the segment
            mid_x = (x1 + x2) / 2.0
            mid_y = (y1 + y2) / 2.0

            # Must be near the centre of the crop
            if abs(mid_x - cx) > margin_x or abs(mid_y - cy) > margin_y:
                continue

            # Classify by angle magnitude (0-90)
            flat_angle = abs(math.degrees(math.atan2(abs(dy), abs(dx))))
            if flat_angle < self._SLASH_MIN or flat_angle > self._SLASH_MAX:
                continue   # too horizontal or too vertical

            # Distinguish / vs \ by sign of dy/dx product
            # / slope → dx and dy have OPPOSITE signs (going upper-right or lower-left)
            # \ slope → dx and dy have SAME sign (going lower-right or upper-left)
            if dx == 0:
                continue

            same_sign = (dx > 0) == (dy > 0)
            if same_sign:
                bslash_found = True
            else:
                slash_found = True

        return slash_found, bslash_found
