"""
behavior_analyzer.py
Fuses emotion, walking speed, direction history, and head-checking patterns
to produce a final behavioral threat assessment with activity classification.
"""
import time
import config


class BehaviorAnalyzer:
    """
    Analyzes behavioral data per person to classify activity and compute threat level.
    Inputs: TrackedPerson objects, emotion, gesture result
    Outputs: activity_label, threat_level, event_type, event_tags
    """

    # Speed thresholds aligned with config
    RUNNING_SPEED = config.SPEED_FAST_THRESHOLD       # px/s
    NORMAL_SPEED  = config.SPEED_NORMAL_THRESHOLD     # px/s

    # Emotion groups we care about – confidence must exceed this floor
    EMOTION_THRESHOLD = 0.65
    TARGET_EMOTIONS   = {"Fear", "Angry", "Sad"}

    # How many consecutive direction reversals in the centroid history counts as "head checking"
    HEAD_CHECK_REVERSALS = 3

    def __init__(self):
        # Per-tracker-ID state: {obj_id: {"last_speed": float, "last_speed_time": float, "direction_history": []}}
        self._state: dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, tracked_objects: dict, emotion: str, emotion_conf: float,
                 gesture: str) -> dict:
        """
        Returns a verdict dict:
            activity        str   e.g. "RUNNING", "WALKING", "SUSPICIOUS_LOITER", "ACCIDENT", "IDLE"
            threat_level    str   "Low" | "Medium" | "High" | "Critical"
            event_type      str   suitable for alert payload
            threat_tags     list  list of descriptive flag strings
            emotion_group   str   "Fear" | "Angry" | "Sad" | "Neutral"
        """
        threat_tags = []
        activity    = "IDLE"
        threat_level = "Low"
        event_type   = None
        emotion_group = "Neutral"

        # ---- Gesture: hardest override ----
        if gesture == "X_GESTURE":
            return {
                "activity": "DISTRESS_SIGNAL",
                "threat_level": "Critical",
                "event_type": "X_GESTURE_EMERGENCY",
                "threat_tags": ["X_HAND_GESTURE", "IMMEDIATE_HELP_REQUIRED"],
                "emotion_group": emotion_group,
            }

        # ---- Emotion filtering ----
        if emotion in self.TARGET_EMOTIONS and emotion_conf >= self.EMOTION_THRESHOLD:
            emotion_group = emotion
            if emotion == "Angry":
                threat_tags.append("ANGER_DETECTED")
                threat_level = "Medium"
            elif emotion == "Fear":
                threat_tags.append("FEAR_DETECTED")
                threat_level = "Medium"
            elif emotion == "Sad":
                threat_tags.append("SAD_DETECTED")
                threat_level = "Low"

        if not tracked_objects:
            return self._build_result(activity, threat_level, event_type,
                                      threat_tags, emotion_group)

        # ---- Per-person analysis ----
        max_speed   = 0.0
        accident    = False
        running     = False
        head_check  = False
        loitering   = False

        for obj_id, person in tracked_objects.items():
            state = self._state.setdefault(obj_id, {
                "prev_speed": 0.0,
                "fast_frames": 0,
                "direction_history": [],
                "accel_time": None,
            })

            spd = person.current_speed_px_s
            max_speed = max(max_speed, spd)

            # --- Running detection ---
            if spd >= self.RUNNING_SPEED:
                state["fast_frames"] += 1
            else:
                state["fast_frames"] = max(0, state["fast_frames"] - 1)

            if state["fast_frames"] >= 3:
                running = True
                threat_tags.append("RUNNING")

            # --- Accident / fall detection ---
            # A sudden deceleration from FAST -> STATIONARY in ≤ 1 second
            prev_spd = state["prev_speed"]
            prev_time = state.get("accel_time") or time.time()

            if prev_spd >= self.RUNNING_SPEED and spd < self.NORMAL_SPEED:
                dt = time.time() - prev_time
                if dt < 1.5:
                    # Also check bounding box aspect ratio — a fallen person is wider than tall
                    bx, by, bw, bh = person.bbox
                    if bw > bh:
                        accident = True
                        threat_tags.append("POSSIBLE_ACCIDENT_FALL")

            if spd >= self.RUNNING_SPEED:
                state["accel_time"] = time.time()

            state["prev_speed"] = spd

            # --- Head-checking detection ---
            # Detect rapid left-right direction reversals in centroid X
            history = state["direction_history"]
            if person.direction in ("left", "right"):
                history.append(person.direction)
                if len(history) > 10:
                    history.pop(0)

            reversals = sum(
                1 for i in range(1, len(history)) if history[i] != history[i - 1]
            )
            if reversals >= self.HEAD_CHECK_REVERSALS:
                head_check = True
                threat_tags.append("HEAD_CHECKING")

            # --- Suspicious loitering ---
            loiter_sec = person.loitering_time()
            if loiter_sec >= config.LOITERING_THRESHOLD_SEC:
                loitering = True
                threat_tags.append(f"LOITERING_{int(loiter_sec)}s")

        # ---- Activity label and event type classification ----
        if accident:
            activity     = "ACCIDENT"
            event_type   = "ACCIDENT_DETECTED"
            threat_level = "High"
        elif running and head_check:
            activity     = "FLEEING"
            event_type   = "SUSPICIOUS_ACTIVITY"
            threat_level = "High"
            threat_tags.append("FLEEING")
        elif running:
            activity     = "RUNNING"
            event_type   = "RAPID_MOTION"
            threat_level = max_threat(threat_level, "Medium")
        elif loitering and "FEAR_DETECTED" in threat_tags:
            activity     = "DISTRESSED_LOITER"
            event_type   = "SUSPICIOUS_ACTIVITY"
            threat_level = "High"
        elif loitering:
            activity     = "SUSPICIOUS_LOITER"
            event_type   = "SUSPICIOUS_ACTIVITY"
            threat_level = max_threat(threat_level, "Medium")
        elif head_check:
            activity     = "LOOKING_BEHIND"
            event_type   = "SUSPICIOUS_ACTIVITY"
            threat_level = max_threat(threat_level, "Medium")
        elif emotion_group in ("Fear", "Angry", "Sad"):
            activity   = "EMOTIONAL_DISTRESS"
            event_type = f"EMOTION_{emotion_group.upper()}"
            threat_level = max_threat(threat_level, "Medium")
        elif tracked_objects:
            activity = "WALKING"

        return self._build_result(activity, threat_level, event_type,
                                  threat_tags, emotion_group)

    def cleanup_missing(self, active_ids: set):
        """Remove state for persons no longer tracked."""
        for oid in list(self._state.keys()):
            if oid not in active_ids:
                del self._state[oid]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_result(self, activity, threat_level, event_type, threat_tags, emotion_group):
        return {
            "activity":     activity,
            "threat_level": threat_level,
            "event_type":   event_type,
            "threat_tags":  list(set(threat_tags)),
            "emotion_group": emotion_group,
        }


def max_threat(current: str, candidate: str) -> str:
    """Returns the higher of two threat level strings."""
    order = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}
    return current if order.get(current, 0) >= order.get(candidate, 0) else candidate
