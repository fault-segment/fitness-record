from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from loguru import logger

from app.config import settings

connect_args = {
    "ssl": {
        "ssl_verify_cert": True,
        "ssl_verify_identity": True,
        "ssl_ca": settings.tidb_ca_path,
    }
} if settings.tidb_ca_path else {"ssl": True}

engine = create_async_engine(
    URL.create(
        drivername="mysql+asyncmy",
        username=settings.tidb_user,
        password=settings.tidb_password,
        host=settings.tidb_host,
        port=settings.tidb_port,
        database=settings.tidb_database,
    ),
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,   # 检出连接前 SELECT 1 检测可用性，自动重建断连
    pool_recycle=300,     # 5 分钟后回收连接，防止 Serverless 休眠后 stale
    connect_args=connect_args,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            logger.exception("Session error")
            raise
        finally:
            await session.close()


async def init_db():
    from app.models import User, FoodRecord, FoodItem  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")
