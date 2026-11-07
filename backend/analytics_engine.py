import datetime as dt
from collections import Counter, defaultdict
from typing import Any, Dict, List

import sqlite3

from .database import get_db


def _utcnow_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def get_basic_analytics() -> Dict[str, Any]:
    """
    Backwards-compatible basic analytics used by the Phase 2 dashboard.
    """
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM events ORDER BY created_at DESC")
        rows = cur.fetchall()

        cur2 = conn.execute("SELECT COUNT(*) as c FROM tower_status")
        tower_row = cur2.fetchone()

    total_events = len(rows)
    high = sum(1 for r in rows if r["risk_level"] == "High")
    med = sum(1 for r in rows if r["risk_level"] == "Medium")
    low = sum(1 for r in rows if r["risk_level"] == "Low")

    emotion_distribution: Counter[str] = Counter(r["emotion"] for r in rows)

    last_event_ts = rows[0]["created_at"] if rows else None
    edge_online = False
    if last_event_ts:
        try:
            last_dt = dt.datetime.fromisoformat(last_event_ts.replace("Z", ""))
            edge_online = (dt.datetime.utcnow() - last_dt) <= dt.timedelta(seconds=20)
        except Exception:
            edge_online = False

    return {
        "success": True,
        "total_events": total_events,
        "high_risk_count": high,
        "medium_risk_count": med,
        "low_risk_count": low,
        "emotion_distribution": dict(emotion_distribution),
        "edge_online": edge_online,
        "last_event_timestamp": last_event_ts,
        "total_registered_towers": tower_row["c"] if tower_row else 0,
        "generated_at": _utcnow_iso(),
    }


def get_advanced_analytics() -> Dict[str, Any]:
    """
    Advanced analytics for charts and trend visualizations.
    """
    since = (dt.datetime.utcnow() - dt.timedelta(hours=24)).replace(microsecond=0)
    since_iso = since.isoformat()

    with get_db() as conn:
        cur: sqlite3.Cursor = conn.execute(
            """
            SELECT tower_id, emotion, risk_level, created_at
            FROM events
            WHERE created_at >= ?
            ORDER BY created_at ASC
            """,
            (since_iso,),
        )
        rows = cur.fetchall()

    # Events per hour
    per_hour: Dict[str, int] = defaultdict(int)
    risk_trend: Dict[str, Dict[str, int]] = defaultdict(lambda: {"High": 0, "Medium": 0, "Low": 0})
    emotion_trend: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    tower_counter: Counter[str] = Counter()

    for r in rows:
        created_at = r["created_at"]
        try:
            t = dt.datetime.fromisoformat(created_at.replace("Z", ""))
        except Exception:
            continue
        hour_bucket = t.replace(minute=0, second=0, microsecond=0).isoformat() + "Z"
        per_hour[hour_bucket] += 1

        risk = r["risk_level"]
        emotion = r["emotion"]
        tower = r["tower_id"]

        risk_trend[hour_bucket][risk] += 1
        emotion_trend[hour_bucket][emotion] += 1
        tower_counter[tower] += 1

    # Normalize for frontend chart consumption
    sorted_hours: List[str] = sorted(per_hour.keys())

    risk_series = {
        "labels": sorted_hours,
        "high": [risk_trend[h]["High"] for h in sorted_hours],
        "medium": [risk_trend[h]["Medium"] for h in sorted_hours],
        "low": [risk_trend[h]["Low"] for h in sorted_hours],
    }

    # Collect all emotions present
    all_emotions = sorted({e for by_hour in emotion_trend.values() for e in by_hour.keys()})
    emotion_series = {
        "labels": sorted_hours,
        "emotions": all_emotions,
        "series": {
            e: [emotion_trend[h].get(e, 0) for h in sorted_hours] for e in all_emotions
        },
    }

    most_active_tower = None
    if tower_counter:
        most_active_tower = tower_counter.most_common(1)[0][0]

    return {
        "success": True,
        "events_per_hour": {"labels": sorted_hours, "counts": [per_hour[h] for h in sorted_hours]},
        "risk_trend": risk_series,
        "emotion_trend": emotion_series,
        "most_active_tower": most_active_tower,
        "generated_at": _utcnow_iso(),
    }

