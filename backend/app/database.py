from urllib.parse import urlparse, parse_qs

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def _build_connect_args() -> dict:
    """构建 SSL 连接参数"""
    if settings.tidb_ca_path:
        return {
            "ssl": {
                "ssl_verify_cert": True,
                "ssl_verify_identity": True,
                "ssl_ca": settings.tidb_ca_path,
            }
        }
    return {"ssl": True}


def _build_url() -> URL:
    """从 DATABASE_URL 构建 SQLAlchemy URL，避免在连接字符串中暴露密码"""
    parsed = urlparse(settings.database_url)
    return URL.create(
        drivername=f"{parsed.scheme}",
        username=parsed.username,
        password=parsed.password,
        host=parsed.hostname,
        port=parsed.port or 4000,
        database=parsed.path.lstrip("/"),
    )


engine = create_async_engine(
    _build_url(),
    echo=False,
    pool_size=5,
    max_overflow=10,
    connect_args=_build_connect_args(),
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    from app.models import User, FoodRecord, FoodItem  # noqa: F401  # ensure models loaded
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
