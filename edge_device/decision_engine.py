"""
decision_engine.py
Responsible for fusing multimodal inputs (time of day, motion, face, emotion) 
to determine if the situation is safe, suspicious, or requires tracking.
"""
import time
import logging
import config

logger = logging.getLogger(__name__)

class DecisionEngine:
    def __init__(self, hardware_controller):
        self.hw = hardware_controller
        self.last_event_time = 0
        self.current_mode = "DAY" # "DAY" or "NIGHT"
        self.tracking_active = False
        
        # Out-of-frame tracking memory
        self.last_target_direction = "stationary"
        self.last_target_speed_label = "stationary"
        self.frames_since_target_lost = 0

    def evaluate(self, motion_data, face_data, tracked_objects, primary_target, frame_brightness=128, pir_motion=False):
        """
        motion_data: tuple (detected, speed, direction, x_center, blob_count)
        face_data: tuple (emotion, confidence, faces_count)
        tracked_objects: dict of active TrackedPersons
        primary_target: TrackedPerson (best target to follow)
        frame_brightness: int (0-255) average pixel brightness
        pir_motion: bool (Direct hardware PIR sensor trigger)
        
        Returns:
            event_type (str or None): If an event should be triggered.
            risk_level (str): "Low", "Medium", "High"
            action (str): Description of the action taken locally.
            servo_angle (int): The evaluated servo angle.
            brightness (int): The evaluated LED brightness.
        """
        mot_detected, mot_speed, mot_dir, mot_x, blob_count = motion_data
        emotion, emo_conf, face_count = face_data
        
        # Consider motion detected if EITHER software pixel difference OR hardware PIR triggers
        any_motion = mot_detected or pir_motion
        
        person_count = len(tracked_objects)
        
        # Determine Day/Night mode based on the physical LDR sensor or Dashboard Override.
        is_dark_sensor = self.hw.is_dark()
        
        # Apply Override if active
        if getattr(config, "OVERRIDE_MODE", "AUTO") == "DAY":
            is_dark = False
            logger.debug("OVERRIDE ACTIVE: Forcing DAY mode")
        elif getattr(config, "OVERRIDE_MODE", "AUTO") == "NIGHT":
            is_dark = True
            logger.debug("OVERRIDE ACTIVE: Forcing NIGHT mode")
        else:
            is_dark = is_dark_sensor
        
        now = time.time()
        
        # --- Time-Based Anti-Bounce ---
        # When the floodlight turns on, the physical LDR will see the light and instantly report "Day" (is_dark_sensor = False).
        # We must prevent it from shutting down the light immediately.
        if self.current_mode == "NIGHT":
            if not is_dark_sensor: # Looks like Day
                # Check if it has been "Day" for more than 5 seconds straight
                if not hasattr(self, 'day_candidate_start'):
                    self.day_candidate_start = now
                elif (now - self.day_candidate_start) < 5.0:
                    is_dark = True # FORCE it to stay night (bounce prevention)
                else:
                    is_dark = False # 5 seconds of sustained light! Transition to Day. 
            else:
                # It's actually dark, reset the candidate timer
                if hasattr(self, 'day_candidate_start'):
                    del self.day_candidate_start
                is_dark = True

        if is_dark != (self.current_mode == "NIGHT"):
            logger.info(f"[Decision] Mode Shift -> {'NIGHT' if is_dark else 'DAY'} (Cam Brightness: {frame_brightness:.1f}, LDR: {is_dark_sensor})")
            
        self.current_mode = "NIGHT" if is_dark else "DAY"
        
        # Sensor rules
        pir_active = self.hw.is_motion_detected()
        
        # Enforce strict hardware relay cutoffs
        self.hw.set_day_night_mode(is_dark)
        
        # Base state
        brightness = config.DAY_BRIGHTNESS if not is_dark else config.NIGHT_BRIGHTNESS_IDLE
        event_type = None
        risk_level = "Low"
        action = "Monitoring"
        servo_angle = self.hw.current_servo_angle
        indicator_on = False

        # Update tracking memory
        if primary_target is not None:
            self.last_target_direction = primary_target.direction
            self.last_target_speed_label = primary_target.speed_label
            self.frames_since_target_lost = 0
        else:
            self.frames_since_target_lost += 1

        # ----- SERVO & LIGHTING EXECUTION (NIGHT ONLY) -----
        if self.current_mode == "NIGHT":
            # 1. BRIGHTNESS LOCK LOGIC (Stops the strobing / IR interference issue)
            # If we see a person OR the PIR fires, push to 100% and lock it for 5 solid seconds.
            if person_count > 0 or pir_active:
                brightness = config.NIGHT_BRIGHTNESS_ACTIVE
                indicator_on = True
                self.brightness_lock_time = now 
            elif hasattr(self, 'brightness_lock_time') and (now - self.brightness_lock_time) < 5.0:
                # Hold brightness for 5 seconds after they leave to prevent blinking
                brightness = config.NIGHT_BRIGHTNESS_ACTIVE
                indicator_on = True
            else:
                brightness = config.NIGHT_BRIGHTNESS_IDLE
                indicator_on = False
                
            # Apply Mosfet Override if active
            if getattr(config, "OVERRIDE_MOSFET", "AUTO") == "FULL":
                brightness = config.NIGHT_BRIGHTNESS_ACTIVE
                indicator_on = True
                logger.debug("MOSFET OVERRIDE ACTIVE: Forcing 100% brightness")

            # Default to maintaining the current angle unless we actively calculate a new destination
            target_servo_angle = self.hw.current_servo_angle

            # 2. TRACKING PRIORITY LOGIC
            # Priority A: Camera explicitly tracking a person (Deep Learning only, NO openCV shadows!)
            if person_count > 0:
                self.frames_since_target_lost = 0
                
                # A) Calculate the mathematical center of the group
                avg_cx = sum([p.centroids[-1][0] for p in tracked_objects.values()]) / person_count
                
                # B) Estimate average velocity vector to predict walking path
                avg_dx_dt = 0
                valid_speeds = 0
                for p in tracked_objects.values():
                    if len(p.centroids) >= 2 and len(p.timestamps) >= 2:
                        dx = p.centroids[-1][0] - p.centroids[0][0]
                        dt = p.timestamps[-1] - p.timestamps[0]
                        if dt > 0:
                            avg_dx_dt += (dx / dt)
                            valid_speeds += 1
                
                if valid_speeds > 0:
                    avg_dx_dt /= valid_speeds
                    
                # C) Exact Physical Linear Mapping (Aligned to 40-deg Camera Mount)
                # The user's camera is statically mounted looking RIGHT (40 degrees).
                # Assuming a 60-degree Field of View: 
                # Left edge of camera (X=0) = 70 degrees
                # Center of camera (X=640)  = 40 degrees
                
                # Formula maps X=0 to 70 deg, and X=1280 to 40 deg.
                target_base_angle = 70 - ((avg_cx / config.IMAGE_WIDTH) * 30)
                
                # Dynamic predictive lead based on human walking speed
                pixels_ahead = avg_dx_dt * 1.5  
                predictive_angle_offset = (pixels_ahead / config.IMAGE_WIDTH) * 30  
                
                # Because rotating right means lowering the angle towards 40, a positive dx (moving right) must be subtracted.
                target_servo_angle = target_base_angle - predictive_angle_offset
                
                self.tracking_active = True
                
                if person_count > 1:
                    action = f"Group Tracking {person_count} subjects (angle={int(target_servo_angle)})"
                elif primary_target is not None:
                    action = f"Active tracing ID:{primary_target.obj_id} (predict_v={int(avg_dx_dt)})"
                else:
                    action = f"Tracing target... (x={int(avg_cx)})"
                
            # Priority B: Predictive Sweeping Off-Camera
            elif self.frames_since_target_lost < (config.FRAMERATE * 4):
                # Target just left the camera frame. Predictively glide the light based on last known direction.
                step = 1.0 if self.last_target_speed_label != "fast" else 3.0
                
                if self.last_target_direction == "left":
                    target_servo_angle += step # Keep pushing towards 180
                elif self.last_target_direction == "right":
                    target_servo_angle -= step # Keep pushing towards 40
                    
                action = f"Predictive off-camera sweeping ({self.last_target_direction})"
                
            # Priority C: Hardware PIR Sensor (Blind Left Zone) 
            # If PIR is active, it ruthlessly overrides raw camera shadows. 
            # This completely destroys the "bounce-back" loop you just described!
            elif pir_active:
                target_servo_angle = 180
                action = "PIR Motion Detected (Left blindzone 180-deg sweep)"
                self.tracking_active = True
                
            # Priority D: Raw Camera Motion Fallback 
            # If no AI human detected, and no PIR hardware detected, but pixels are moving
            elif mot_detected:
                if hasattr(self, 'last_commanded_angle'):
                    is_moving = abs(self.hw.current_servo_angle - self.last_commanded_angle) > 2
                else:
                    is_moving = False
                    
                if not is_moving:
                    # Map raw motion X coordinate to the physical 40-70 degree camera window
                    target_base_angle = 70 - ((mot_x / config.IMAGE_WIDTH) * 30)
                    target_servo_angle = target_base_angle
                    
                    self.tracking_active = True
                    action = f"Aiming at Raw Camera Motion {mot_dir} (x={mot_x})"
                else:
                    # If moving, maintain the sweep trajectory 
                    target_servo_angle = getattr(self, 'last_commanded_angle', self.hw.current_servo_angle)
                    action = "Ignoring moving camera shadows during sweep."

            # Priority E: Idle Position (No humans, no PIR, no predictors)
            else:
                self.tracking_active = False
                target_servo_angle = config.SERVO_DEFAULT_ANGLE # Return to 110
                action = "Returning to idle forward position"
                
            # 3. KINEMATIC SWEEPER 
            # Replaces the low-pass filter and direct-snap methods.
            # Moves the servo aggressively toward the target, but capped at a physical speed limit (e.g., 5 degrees per frame).
            diff = target_servo_angle - self.hw.current_servo_angle
            
            if abs(diff) > config.SERVO_STEP:
                # Move by maximum allowed physical step
                step_direction = 1 if diff > 0 else -1
                servo_angle = self.hw.current_servo_angle + (config.SERVO_STEP * step_direction)
            else:
                # Close enough, snap to target
                servo_angle = target_servo_angle

        if servo_angle < config.SERVO_MIN_ANGLE: servo_angle = config.SERVO_MIN_ANGLE
        if servo_angle > config.SERVO_MAX_ANGLE: servo_angle = config.SERVO_MAX_ANGLE

        # ----- ADVANCED THREAT ASSESSMENT HEURISTICS -----
        now = time.time()
        cooldown_passed = (now - self.last_event_time) > config.MOTION_COOLDOWN_SEC

        if cooldown_passed:
            # Check maximum speed among tracked people
            max_speed_label = "stationary"
            max_loiter_time = 0.0
            
            for p in tracked_objects.values():
                if p.speed_label == "fast": max_speed_label = "fast"
                if p.speed_label == "normal" and max_speed_label != "fast": max_speed_label = "normal"
                
                lt = p.loitering_time()
                if lt > max_loiter_time:
                    max_loiter_time = lt
            
            # Rule 1: Fast/Running at Night
            if person_count > 0 and max_speed_label == "fast" and self.current_mode == "NIGHT":
                event_type = "Rapid_Movement_Night"
                risk_level = "Medium"
                action = "Human identified running at high speed"
                brightness = 100
                
            # Rule 2: Prolonged Loitering
            elif person_count > 0 and max_loiter_time > config.LOITERING_THRESHOLD_SEC:
                event_type = "Prolonged_Loitering"
                risk_level = "High"  # Explicitly trigger video save (High Risk)
                action = f"Human loitering detected ({round(max_loiter_time)}s)"
                
            # Rule 3: Crowding / Gathering
            elif person_count >= 3:
                event_type = "Crowd_Gathering"
                risk_level = "Medium"
                action = f"Alerted gathering ({person_count} persons)"
                
            # Rule 4: Emotion + Activity Context
            elif face_count > 0:
                if emotion in ["Angry", "Fear"] and emo_conf > 0.60:
                    event_type = "Possible_Conflict" if person_count > 1 else "Distress_Suspected"
                    risk_level = "High"  # Explicitly trigger video save
                    action = f"Alerted based on emotion ({emotion})"
                    if self.current_mode == "NIGHT":
                        brightness = 100
                elif emotion == "Sad" and emo_conf > 0.60:
                    event_type = "Distress_Suspected"
                    risk_level = "High" # Trigger video save for Sad too
                    action = f"Person appears sad/distressed"
                
        if event_type:
            self.last_event_time = now
            
        return event_type, risk_level, action, servo_angle, brightness, indicator_on
