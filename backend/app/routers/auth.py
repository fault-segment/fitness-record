from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from loguru import logger

from app.config import settings
from app.database import get_session
from app.middleware import create_token
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(code: dict[str, str], session: AsyncSession = Depends(get_session)):
    """微信登录，code 换 openid，返回 JWT"""
    wx_code = code.get("code")
    if not wx_code:
        logger.warning("Login attempt with empty code")
        raise HTTPException(status_code=400, detail="缺少 code")

    # 调用微信接口换取 openid
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.weixin.qq.com/sns/jscode2session",
                params={
                    "appid": settings.wechat_appid,
                    "secret": settings.wechat_secret,
                    "js_code": wx_code,
                    "grant_type": "authorization_code",
                },
            )
            data = resp.json()
    except Exception:
        logger.exception("WeChat API call failed")
        raise HTTPException(status_code=502, detail="微信服务暂时不可用")

    openid = data.get("openid")
    if not openid:
        errmsg = data.get("errmsg", "微信登录失败")
        logger.warning("WeChat code2session failed: {errmsg}", errmsg=errmsg)
        raise HTTPException(status_code=400, detail=errmsg)

    # 查找或创建用户
    result = await session.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    is_new = user is None

    if is_new:
        user = User(openid=openid)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info("New user registered: user_id={id}", id=user.id)
    else:
        logger.debug("User logged in: user_id={id}", id=user.id)

    token = create_token(user.id)
    return {"token": token, "user_id": user.id, "is_new": is_new}
