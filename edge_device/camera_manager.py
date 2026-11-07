"""
camera_manager.py
Manages the Pi Camera Module 3 via Picamera2.
Grabs frames as NumPy arrays and converts to BGR for OpenCV.
"""
import logging
import cv2
import numpy as np
import threading
try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except ImportError:
    PICAMERA_AVAILABLE = False
    logging.warning("Picamera2 not available. Camera features will be simulated.")

import config

logger = logging.getLogger(__name__)

class CameraManager:
    def __init__(self):
        self.picam2 = None
        self.is_running = False
        if PICAMERA_AVAILABLE:
            try:
                self.picam2 = Picamera2()
                # Configure stream, typically capturing array output
                cam_config = self.picam2.create_video_configuration(
                    main={"size": (config.IMAGE_WIDTH, config.IMAGE_HEIGHT), "format": "XBGR8888"}
                )
                self.picam2.configure(cam_config)
                
                # CRITICAL HARDWARE FIX for IMX708 PDAF Freezes:
                # The heavy AI CPU load disrupts the I2C hardware timing of the PDAF Autofocus,
                # crashing libcamera after ~20s. We physically disable AutoFocus and lock to Infinity.
                # (This is perfect for an 8m high Streetlight Edge Device anyway).
                try:
                    self.picam2.set_controls({"AfMode": 0, "LensPosition": 0.0})
                except Exception as c_err:
                    logger.warning(f"Could not lock Lens AF controls: {c_err}")
                    
                logger.info("Picamera2 configured successfully (AF Disabled).")
            except Exception as e:
                logger.error(f"Failed to configure Picamera2: {e}")
                self.picam2 = None

    def start(self):
        if self.picam2 and not self.is_running:
            try:
                self.picam2.start()
                self.is_running = True
                logger.info("Camera started.")
            except Exception as e:
                logger.error(f"Failed to start camera: {e}")

    def stop(self):
        if self.picam2 and self.is_running:
            try:
                def force_stop():
                    try:
                        self.picam2.stop()
                    except Exception as inner_e:
                        logger.error(f"Inner camera stop exception: {inner_e}")
                
                # Wrap the unreliable libcamera binding in a strict timeout thread
                t = threading.Thread(target=force_stop, daemon=True)
                t.start()
                t.join(timeout=2.0)
                
                if t.is_alive():
                    logger.warning("Camera stop thread timed out. Forcing shutdown.")
                
                self.is_running = False
                logger.info("Camera stopped cleanly.")
            except Exception as e:
                logger.error(f"Failed to stop camera gracefully: {e}")
                
    def get_frame(self):
        """
        Retrieves a frame from the camera.
        Converts the XBGR8888 (RGBA or RGBX) format from Picamera2 into standard OpenCV BGR.
        Returns:
            np.ndarray: BGR image, or None if failed.
        """
        if not self.is_running or not self.picam2:
            return None
        
        try:
            # Capture array from picamera2. Default format often ends up as 4 channels.
            frame = self.picam2.capture_array('main')
            
            # Convert 4 channel to 3 channel BGR
            if len(frame.shape) == 3 and frame.shape[2] == 4:
                # Based on typical Picamera2 behavior array shape is (H, W, 4)
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
                return frame_bgr
            elif len(frame.shape) == 3 and frame.shape[2] == 3:
                # Already RGB or BGR.
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                return frame_bgr
            
            return frame
        except Exception as e:
            logger.error(f"Error capturing frame: {e}")
            return None
