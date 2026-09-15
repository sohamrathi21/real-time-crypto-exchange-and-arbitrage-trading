import json
import logging
from sqlalchemy import String, Float, BigInteger, JSON, Index, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from .models import now_ms

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class Record(Base):
    __tablename__ = "records"
    id: Mapped[str] = mapped_column(String(240), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(80), default="", index=True)
    exchange: Mapped[str] = mapped_column(String(80), default="", index=True)
    timestamp: Mapped[int] = mapped_column(BigInteger, index=True)
    opportunity_id: Mapped[str] = mapped_column(String(240), default="", index=True)
    net_edge: Mapped[float] = mapped_column(Float, default=0, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (Index("ix_kind_time", "kind", "timestamp"),)


class Repository:
    """Typed record categories keep demo schema small; JSON payloads retain full audit fields."""

    def __init__(self, url):
        self.engine = create_async_engine(url, pool_pre_ping=True)
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)
        self.ready = False

    async def initialize(self):
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.ready = True

    async def put_many(self, records):
        async with self.session() as session:
            for record in records:
                await session.merge(Record(**record))
            await session.commit()

    async def get(self, kind, identifier):
        async with self.session() as session:
            row = await session.get(Record, f"{kind}:{identifier}")
            return row.payload if row else None

    async def list(self, kind, limit=10000):
        async with self.session() as session:
            rows = await session.scalars(
                select(Record)
                .where(Record.kind == kind)
                .order_by(Record.timestamp.desc())
                .limit(limit)
            )
            return [row.payload for row in rows]

    async def close(self):
        await self.engine.dispose()


def record(kind, identifier, payload, **fields):
    return dict(
        id=f"{kind}:{identifier}",
        kind=kind,
        timestamp=fields.pop("timestamp", now_ms()),
        payload=payload,
        **fields,
    )
