from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from app.config import settings

security = HTTPBearer(auto_error=False)


def create_token(user_id: int) -> str:
    payload = {"user_id": user_id}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload["user_id"]
    except jwt.PyJWTError:
        logger.warning("Invalid or expired token")
        raise HTTPException(status_code=401, detail="token 无效或已过期")


async def get_user_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> int:
    if credentials is None:
        logger.warning("Request missing auth credentials")
        raise HTTPException(status_code=401, detail="请先登录")
    return verify_token(credentials.credentials)
