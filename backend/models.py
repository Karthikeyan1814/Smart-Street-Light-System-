from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class Event:
    """
    In-memory representation of a single lighting system event.

    This mirrors the SQLite `events` table and provides a clean model
    for serializing to API responses.
    """

    id: Optional[int]
    tower_id: str
    location: str
    event_type: str
    emotion: str
    confidence: float
    risk_level: str
    llm_summary: Optional[str]
    recommended_action: Optional[str]
    video_path: Optional[str]
    created_at: str
    processed_at: Optional[str]
    # Phase 2: Behavioral AI fields
    gesture_detected: Optional[str] = "NONE"
    activity: Optional[str] = "UNKNOWN"
    threat_tags: Optional[str] = ""
    emotion_group: Optional[str] = "Neutral"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def row_to_event(row) -> Event:
    return Event(
        id=row["id"],
        tower_id=row["tower_id"],
        location=row["location"],
        event_type=row["event_type"],
        emotion=row["emotion"],
        confidence=row["confidence"],
        risk_level=row["risk_level"],
        llm_summary=row["llm_summary"],
        recommended_action=row["recommended_action"],
        video_path=row["video_path"],
        created_at=row["created_at"],
        processed_at=row["processed_at"],
        gesture_detected=row["gesture_detected"] if "gesture_detected" in row.keys() else "NONE",
        activity=row["activity"] if "activity" in row.keys() else "UNKNOWN",
        threat_tags=row["threat_tags"] if "threat_tags" in row.keys() else "",
        emotion_group=row["emotion_group"] if "emotion_group" in row.keys() else "Neutral",
    )

