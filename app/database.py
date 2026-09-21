from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


_engine = None
_async_session = None


def _get_engine():
    global _engine
    if _engine is None:
        from app.config import get_settings
        settings = get_settings()
        url = settings.async_database_url
        connect_args = {}
        if "neon" in url or "neon.tech" in url:
            import ssl
            ssl_ctx = ssl.create_default_context()
            connect_args["ssl"] = ssl_ctx
        _engine = create_async_engine(url, echo=False, connect_args=connect_args)
    return _engine


def _get_session_factory():
    global _async_session
    if _async_session is None:
        _async_session = async_sessionmaker(_get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _async_session


async def get_db():
    factory = _get_session_factory()
    async with factory() as session:
        yield session
