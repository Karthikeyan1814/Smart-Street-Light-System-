import json
import logging
from typing import Any, Dict

from .config import settings

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - dependency optional at runtime
    OpenAI = None  # type: ignore


def _rule_based_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback, deterministic rule-based "LLM" for environments without real LLM access.
    """
    emotion = payload.get("emotion", "Neutral")
    confidence = float(payload.get("confidence", 0.5))
    location = payload.get("location", "Unknown location")
    event_type = payload.get("event_type", "Activity")

    if emotion in {"Fear", "Anger"} and confidence >= 0.7:
        risk_level = "High"
        action = "Immediate Response Required: Dispatch security to investigate."
    elif emotion in {"Sad", "Disgust"} or confidence >= 0.5:
        risk_level = "Medium"
        action = "Monitor the area via CCTV and notify on-ground staff."
    else:
        risk_level = "Low"
        action = "No immediate action required. Continue passive monitoring."

    summary = (
        f"Detected {emotion} with confidence {confidence:.2f} at {location} "
        f"during {event_type}. Estimated risk level is {risk_level}."
    )

    return {
        "summary": summary,
        "risk_level": risk_level,
        "recommended_action": action,
    }


def _call_openai_chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call an OpenAI-compatible ChatCompletion endpoint and return structured JSON.
    """
    if OpenAI is None:
        logger.warning("OpenAI client not available, falling back to rule-based engine.")
        return _rule_based_summary(payload)

    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not configured, falling back to rule-based engine.")
        return _rule_based_summary(payload)

    client_kwargs: Dict[str, Any] = {"api_key": settings.OPENAI_API_KEY}
    if settings.OPENAI_API_BASE:
        client_kwargs["base_url"] = settings.OPENAI_API_BASE

    client = OpenAI(**client_kwargs)

    system_prompt = (
        "You are an AI incident analysis engine for a smart city street-lighting platform. "
        "Given a JSON payload describing an event (tower_id, location, event_type, emotion, "
        "confidence, timestamp), you MUST respond with a compact JSON object containing "
        "three fields: summary (string), risk_level (High/Medium/Low), and "
        "recommended_action (string actionable guidance for operators). "
        "Respond with ONLY valid JSON, no markdown or extra text."
    )

    user_content = json.dumps(payload)

    try:
        completion = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
        )
        raw_content = completion.choices[0].message.content or ""
        data = json.loads(raw_content)
        # Basic validation / normalization
        return {
            "summary": str(data.get("summary", "")),
            "risk_level": str(data.get("risk_level", "Medium")),
            "recommended_action": str(data.get("recommended_action", "")),
        }
    except Exception as exc:  # pragma: no cover - network / vendor issues
        logger.exception("LLM call failed, falling back to rule-based engine: %s", exc)
        return _rule_based_summary(payload)


def analyze_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Public API used by the routes layer to obtain an incident analysis.

    It automatically switches between a real LLM integration and a deterministic
    rule-based implementation based on configuration.
    """
    if settings.USE_REAL_LLM:
        return _call_openai_chat(payload)
    return _rule_based_summary(payload)

"""
LLM Engine Module - Rule-based incident summarization.
This module simulates LLM behavior and is structured so it can be
replaced with a real LLM API in the future.
"""

from datetime import datetime
from typing import Dict, Any


def generate_incident_summary(alert_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Generate a human-readable incident summary and structured risk assessment.

    Args:
        alert_data: Dictionary containing alert information.

    Returns:
        Dictionary with 'summary', 'risk_level', and 'recommended_action' keys.
    """
    tower_id = alert_data.get("tower_id", "UNKNOWN")
    location = alert_data.get("location", "Unknown Location")
    event_type = alert_data.get("event_type", "Unknown Event")
    emotion = alert_data.get("emotion", "Unknown")
    confidence = float(alert_data.get("confidence", 0.0) or 0.0)
    timestamp = alert_data.get("timestamp", "")

    # Parse timestamp for better formatting
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        time_str = timestamp

    # Generate summary based on emotion and event type
    emotion_descriptions = {
        "Fear": "individuals showing signs of distress or fear",
        "Anger": "individuals displaying aggressive behavior",
        "Sadness": "individuals appearing distressed or in need of assistance",
        "Surprise": "unexpected activity detected",
        "Happiness": "normal activity observed",
        "Neutral": "standard activity detected",
    }

    event_descriptions = {
        "Suspicious Activity": "suspicious behavior patterns",
        "Emergency": "potential emergency situation",
        "Accident": "traffic or pedestrian accident",
        "Vandalism": "property damage or vandalism",
        "Normal Activity": "routine activity",
    }

    emotion_desc = emotion_descriptions.get(emotion, "activity")
    event_desc = event_descriptions.get(event_type, "event")

    # Generate textual summary
    summary = (
        f"Incident detected at {location} (Tower {tower_id}) on {time_str}. "
        f"Analysis indicates {emotion_desc} with {event_desc}. "
        f"Detection confidence: {confidence:.0%}. "
        f"Event classification: {event_type} with emotional state: {emotion}."
    )

    # Rule-based risk assessment
    risk_level: str
    if event_type == "Emergency" or emotion in {"Fear", "Anger"}:
        risk_level = "High"
    elif event_type in {"Suspicious Activity", "Accident"} or emotion in {"Sadness", "Surprise"}:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    # Lower confidence can reduce risk by one level
    if confidence < 0.4 and risk_level == "High":
        risk_level = "Medium"
    elif confidence < 0.4 and risk_level == "Medium":
        risk_level = "Low"

    # Generate recommended action based on risk level
    if risk_level == "High":
        recommended_action = (
            "Immediate Response Required: Dispatch security personnel and notify "
            "emergency services. Increase lighting intensity to maximum and "
            "prioritize live monitoring for this location."
        )
    elif risk_level == "Medium":
        recommended_action = (
            "Increased Monitoring Recommended: Increase patrol frequency and keep "
            "lighting levels elevated. Review recent incidents in this area."
        )
    else:
        recommended_action = (
            "Standard Monitoring: Maintain routine surveillance and normal "
            "lighting levels. No immediate action required."
        )

    return {
        "summary": summary,
        "risk_level": risk_level,
        "recommended_action": recommended_action,
    }


def process_alert(alert_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for LLM-style processing.

    Args:
        alert_data: Alert data dictionary.

    Returns:
        Dictionary with original alert data plus LLM-generated fields:
        - llm_summary
        - llm_risk_level
        - llm_recommended_action
        - processed_at (UTC ISO timestamp)
    """
    llm_result = generate_incident_summary(alert_data)

    return {
        **alert_data,
        "llm_summary": llm_result["summary"],
        "llm_risk_level": llm_result["risk_level"],
        "llm_recommended_action": llm_result["recommended_action"],
        "processed_at": datetime.utcnow().isoformat() + "Z",
    }


