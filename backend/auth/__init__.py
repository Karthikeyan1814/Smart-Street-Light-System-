"""
Auth package: JWT helpers and API-key auth for edge devices.
"""

from .api_key import api_key_auth  # noqa: F401
from .jwt_handler import (  # noqa: F401
    create_access_token,
    get_current_user,
    require_role,
)

