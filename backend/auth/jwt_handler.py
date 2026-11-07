import datetime as dt
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from ..config import settings
from ..database import get_db


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[dt.timedelta] = None
) -> str:
    to_encode = data.copy()
    expire = dt.datetime.utcnow() + (expires_delta or dt.timedelta(hours=1))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def _get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    from sqlite3 import Row

    with get_db() as conn:
        cur = conn.execute(
            "SELECT id, username, hashed_password, role FROM users WHERE username = ?",
            (username,),
        )
        row: Optional[Row] = cur.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "hashed_password": row["hashed_password"],
            "role": row["role"],
        }


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")  # type: ignore[assignment]
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = _get_user_by_username(username)
    if user is None:
        raise credentials_exception
    return user


def require_role(required_role: str):
    async def dependency(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        role = user.get("role")
        if role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency

