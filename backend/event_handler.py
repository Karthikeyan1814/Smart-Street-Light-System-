"""
Event Handler Module - Manages event storage and retrieval.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List
from config import EVENTS_FILE, STORAGE_DIR


def ensure_storage_exists():
    """Ensure storage directory and events file exist."""
    os.makedirs(STORAGE_DIR, exist_ok=True)
    if not os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, 'w') as f:
            json.dump([], f)


def save_event(event_data: Dict[str, Any]) -> bool:
    """
    Save an event to the events.json file.
    
    Args:
        event_data: Event data dictionary to save
        
    Returns:
        True if successful, False otherwise
    """
    try:
        ensure_storage_exists()
        
        # Read existing events
        if os.path.exists(EVENTS_FILE):
            with open(EVENTS_FILE, 'r') as f:
                events = json.load(f)
        else:
            events = []
        
        # Add new event
        events.append(event_data)
        
        # Write back to file
        with open(EVENTS_FILE, 'w') as f:
            json.dump(events, f, indent=2)
        
        return True
    except Exception as e:
        print(f"Error saving event: {e}")
        return False


def get_all_events(limit: int = None) -> List[Dict[str, Any]]:
    """
    Retrieve all events from storage.
    
    Args:
        limit: Optional limit on number of events to return (most recent first)
        
    Returns:
        List of event dictionaries
    """
    try:
        ensure_storage_exists()
        
        if not os.path.exists(EVENTS_FILE):
            return []
        
        with open(EVENTS_FILE, 'r') as f:
            events = json.load(f)
        
        # Sort by timestamp (most recent first)
        events.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        if limit:
            return events[:limit]
        
        return events
    except Exception as e:
        print(f"Error retrieving events: {e}")
        return []


def get_event_count() -> int:
    """
    Get the total number of events stored.
    
    Returns:
        Number of events
    """
    try:
        events = get_all_events()
        return len(events)
    except:
        return 0

