import time
from collections import defaultdict
from typing import Dict, Tuple

from fastapi import Request

from .config import settings


_requests: Dict[Tuple[str, str], list[float]] = defaultdict(list)


def check_rate_limit(request: Request) -> Tuple[bool, str]:
    """
    Simple in-memory rate limiter keyed by (ip, endpoint_id).

    Returns (allowed, endpoint_id).
    """
    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path

    if request.method == "POST" and path == "/api/auth/login":
        limit = 5
        key = (client_ip, "login")
    elif request.method == "POST" and path == "/api/alert":
        limit = settings.ALERT_RATE_LIMIT_PER_MINUTE
        key = (client_ip, "alert")
    else:
        return True, ""

    now = time.time()
    window_start = now - 60
    history = _requests[key]

    # Drop old entries
    history = [t for t in history if t >= window_start]
    _requests[key] = history

    if len(history) >= limit:
        return False, key[1]

    history.append(now)
    return True, key[1]

