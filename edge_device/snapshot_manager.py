import cv2
import os
import time
import logging
from collections import deque
import threading

import config

logger = logging.getLogger(__name__)

class SnapshotManager:
    def __init__(self, max_files=150):
        self.save_dir = config.SNAPSHOTS_DIR
        self.max_files = max_files
        
        # 15 Seconds of Buffer at nominal 15 FPS
        self.max_frames = int(15 * config.FRAMERATE)
        self.frame_buffer = deque(maxlen=self.max_frames)
        self.buffer_lock = threading.Lock()

    def register_frame(self, frame_bgr):
        """Continually feeds the 20-second rolling ring buffer."""
        if frame_bgr is not None:
            with self.buffer_lock:
                self.frame_buffer.append(frame_bgr.copy())

    def save_snapshot(self, frame_bgr, event_prefix="event"):
        """
        Saves a BGR frame as JPEG. Returns the absolute file path.
        """
        if frame_bgr is None:
            return None
            
        timestamp = int(time.time())
        filename = f"{config.TOWER_ID}_{event_prefix}_{timestamp}.jpg"
        filepath = os.path.join(self.save_dir, filename)
        
        try:
            cv2.imwrite(filepath, frame_bgr)
            logger.info(f"Saved snapshot: {filepath}")
            self._cleanup_old_files('.jpg')
            return filepath
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            return None

    def save_video(self, event_prefix="emergency"):
        """
        Flushes the current 15-sec ring buffer into an MP4 file.
        Returns the absolute file path.
        """
        timestamp = int(time.time())
        # Changing to mp4 with mp4v so it works inherently in HTML5 <video> tags on the React frontend
        filename = f"{config.TOWER_ID}_{event_prefix}_{timestamp}.mp4"
        filepath = os.path.join(self.save_dir, filename)
        
        with self.buffer_lock:
            frames_to_write = list(self.frame_buffer)
            
        if not frames_to_write:
            logger.warning("No frames in buffer to save video.")
            return None
            
        try:
            h, w = frames_to_write[0].shape[:2]
            # H.264 strictly requires even dimensions. Auto-crop 1px if odd.
            w = w if w % 2 == 0 else w - 1
            h = h if h % 2 == 0 else h - 1
            
            # Try multiple browser-optimized codecs
            codecs = ['avc1', 'X264', 'H264']
            out = None
            used_codec = "None"
            
            for c in codecs:
                fourcc = cv2.VideoWriter_fourcc(*c)
                test_out = cv2.VideoWriter(filepath, fourcc, float(config.FRAMERATE), (w, h))
                if test_out.isOpened():
                    out = test_out
                    used_codec = c
                    break
                    
            if not out:
                logger.warning("No H.264 codecs available. Falling back to mp4v (Browsers may show black screens).")
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(filepath, fourcc, float(config.FRAMERATE), (w, h))
                used_codec = "mp4v"
            else:
                logger.info(f"[Success] Video encoded using {used_codec} for browser compatibility.")

            for f in frames_to_write:
                # Resize if we had to adjust for even dimensions
                if f.shape[1] != w or f.shape[0] != h:
                    f = cv2.resize(f, (w, h))
                out.write(f)
            out.release()
            
            logger.info(f"Saved 15s Emergency Video: {filepath}")
            self._cleanup_old_files('.mp4')
            return filepath
        except Exception as e:
            logger.error(f"Failed to save video buffer: {e}")
            return None

    def _cleanup_old_files(self, ext='.jpg'):
        """
        Keeps the folder clean by deleting oldest files beyond max_files.
        """
        try:
            files = [os.path.join(self.save_dir, f) for f in os.listdir(self.save_dir) if f.endswith(ext)]
            if len(files) > self.max_files:
                files.sort(key=lambda x: os.path.getmtime(x))
                files_to_delete = files[:-self.max_files]
                for f in files_to_delete:
                    os.remove(f)
        except Exception as e:
            logger.error(f"Error cleaning snapshots: {e}")
