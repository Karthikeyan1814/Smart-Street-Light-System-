"""
person_tracker.py
Tracks bounding boxes across frames to assign unique IDs, estimate speed (px/s),
determine loitering, and find the primary tracking target.
"""
import time
import math
import config

class TrackedPerson:
    def __init__(self, obj_id, centroid, bbox):
        self.obj_id = obj_id
        self.centroids = [centroid]  # History
        self.timestamps = [time.time()]
        self.bbox = bbox
        self.first_seen = time.time()
        self.disappeared_frames = 0
        
        self.current_speed_px_s = 0.0
        self.speed_label = "stationary"
        self.direction = "static"
        
    def update(self, centroid, bbox):
        self.centroids.append(centroid)
        self.timestamps.append(time.time())
        self.bbox = bbox
        self.disappeared_frames = 0
        
        # Keep history short (last 10 frames approx)
        if len(self.centroids) > 10:
            self.centroids.pop(0)
            self.timestamps.pop(0)
            
        self._calculate_kinematics()
        
    def _calculate_kinematics(self):
        if len(self.centroids) < 2:
            return
            
        # Compare first and last in buffer
        p1 = self.centroids[0]
        p2 = self.centroids[-1]
        t1 = self.timestamps[0]
        t2 = self.timestamps[-1]
        
        dt = t2 - t1
        if dt > 0:
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            dist = math.hypot(dx, dy)
            self.current_speed_px_s = dist / dt
            
            # Label
            if self.current_speed_px_s < config.SPEED_SLOW_THRESHOLD:
                self.speed_label = "stationary"
            elif self.current_speed_px_s < config.SPEED_NORMAL_THRESHOLD:
                self.speed_label = "slow"
            elif self.current_speed_px_s < config.SPEED_FAST_THRESHOLD:
                self.speed_label = "normal"
            else:
                self.speed_label = "fast"
                
            # Direction
            if abs(dx) > abs(dy):
                if dx > 5: self.direction = "right"
                elif dx < -5: self.direction = "left"
            else:
                if dy > 5: self.direction = "down"
                elif dy < -5: self.direction = "up"
        
    def loitering_time(self):
        # We consider them loitering if they are mostly stationary over a duration
        # If they are running back and forth, they are just active, not strictly loitering.
        if self.speed_label in ["stationary", "slow"]:
            return time.time() - self.first_seen
        return 0.0


class CentroidTracker:
    def __init__(self, max_disappeared=5, max_distance=100):
        self.next_object_id = 0
        self.objects = {} # obj_id -> TrackedPerson
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def get_primary_target(self):
        """
        Returns the TrackedPerson that should be followed by the servo.
        A heuristic: Largest bounding box area or longest tracked.
        """
        if len(self.objects) == 0:
            return None
            
        # Example: prioritize largest bbox (closest person)
        def area(p):
            return p.bbox[2] * p.bbox[3]
            
        primary = max(self.objects.values(), key=area)
        return primary

    def update(self, detections):
        """
        detections: list of dicts [{"bbox": (x,y,w,h), "centroid": (cx,cy)}]
        Returns a dictionary of active objects.
        """
        if len(detections) == 0:
            for obj_id in list(self.objects.keys()):
                self.objects[obj_id].disappeared_frames += 1
                if self.objects[obj_id].disappeared_frames > self.max_disappeared:
                    del self.objects[obj_id]
            return self.objects

        input_centroids = [d["centroid"] for d in detections]
        input_bboxes = [d["bbox"] for d in detections]
        
        if len(self.objects) == 0:
            for i in range(len(input_centroids)):
                self.objects[self.next_object_id] = TrackedPerson(self.next_object_id, input_centroids[i], input_bboxes[i])
                self.next_object_id += 1
        else:
            object_ids = list(self.objects.keys())
            object_centroids = [self.objects[oid].centroids[-1] for oid in object_ids]
            
            # Simple greedy distance matching
            used_objects = set()
            used_inputs = set()
            
            for in_idx, in_cent in enumerate(input_centroids):
                best_dist = float('inf')
                best_obj = -1
                
                for obj_idx, obj_cent in enumerate(object_centroids):
                    if object_ids[obj_idx] in used_objects:
                        continue
                    dist = math.hypot(in_cent[0] - obj_cent[0], in_cent[1] - obj_cent[1])
                    if dist < best_dist and dist < self.max_distance:
                        best_dist = dist
                        best_obj = object_ids[obj_idx]
                        
                if best_obj != -1:
                    # Match found
                    self.objects[best_obj].update(in_cent, input_bboxes[in_idx])
                    used_objects.add(best_obj)
                    used_inputs.add(in_idx)
                    
            # Register missing inputs as new objects
            for in_idx in range(len(input_centroids)):
                if in_idx not in used_inputs:
                    self.objects[self.next_object_id] = TrackedPerson(self.next_object_id, input_centroids[in_idx], input_bboxes[in_idx])
                    self.next_object_id += 1
                    
            # Increment missing counters for unmatched objects
            for obj_id in object_ids:
                if obj_id not in used_objects:
                    self.objects[obj_id].disappeared_frames += 1
                    if self.objects[obj_id].disappeared_frames > self.max_disappeared:
                        del self.objects[obj_id]

        return self.objects
