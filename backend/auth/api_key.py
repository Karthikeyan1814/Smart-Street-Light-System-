"""
API-key authentication for edge devices (alerts, heartbeat).
"""

from fastapi import Header, HTTPException, status

from ..config import settings


async def api_key_auth(x_api_key: str = Header(..., alias="X-API-KEY")) -> str:
    """
    API-key based authentication for edge devices only.
    """
    if not x_api_key or x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key
