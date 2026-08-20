from datetime import UTC, datetime

from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


@event.listens_for(Base, "before_insert", propagate=True)
def _set_timestamps_on_insert(_mapper, _connection, target: object) -> None:
    """Prisma @updatedAt has no DB default; set timestamps on insert in Python."""
    now = datetime.now(UTC)
    if hasattr(target, "created_at") and getattr(target, "created_at", None) is None:
        target.created_at = now  # type: ignore[attr-defined]
    if hasattr(target, "updated_at") and getattr(target, "updated_at", None) is None:
        target.updated_at = now  # type: ignore[attr-defined]


@event.listens_for(Base, "before_update", propagate=True)
def _set_updated_at_on_update(_mapper, _connection, target: object) -> None:
    if hasattr(target, "updated_at"):
        target.updated_at = datetime.now(UTC)  # type: ignore[attr-defined]
