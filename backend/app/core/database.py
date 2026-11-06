import uuid
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

engine_kwargs = {"echo": False, "future": True}
if "sqlite" in settings.DATABASE_URL:
    from sqlalchemy.pool import StaticPool
    engine_kwargs.update({
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False}
    })
else:
    engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 10,
        "pool_pre_ping": True
    })

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


class Base(DeclarativeBase):
    """Base declarative class for all unified SaaS entities."""
    pass


async def set_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Enforces PostgreSQL Row-Level Security (RLS) for the current active transaction."""
    if session.bind and session.bind.dialect.name == "postgresql":
        await session.execute(
            text("SET LOCAL app.current_tenant_id = :tenant_id"),
            {"tenant_id": str(tenant_id)}
        )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provides an un-scoped async database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

