from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
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
        # Vercel functions can be frozen and resumed after Neon has closed an
        # idle connection.  A process-local SQLAlchemy pool can then hand a
        # dead asyncpg connection to the next request.  Use one connection per
        # session in serverless; Neon remains responsible for pooling upstream.
        is_vercel = bool(__import__("os").environ.get("VERCEL"))
        engine_kwargs = {
            "echo": False,
            "connect_args": connect_args,
            "pool_pre_ping": True,
        }
        if is_vercel:
            engine_kwargs["poolclass"] = NullPool
        else:
            engine_kwargs["pool_recycle"] = 300
        _engine = create_async_engine(url, **engine_kwargs)
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
