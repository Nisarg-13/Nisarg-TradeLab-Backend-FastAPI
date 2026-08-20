from datetime import UTC, datetime
from typing import Literal

LiveDataStatus = Literal["LIVE", "STALE", "DISCONNECTED"]

HEARTBEAT_DISCONNECTED_MS = 5 * 60 * 1000
SNAPSHOT_STALE_MS = 90 * 1000


def resolve_live_data_status(
    *,
    last_heartbeat_at: datetime | None,
    last_position_snapshot_at: datetime | None,
    now: datetime | None = None,
) -> LiveDataStatus:
    connection_status = resolve_connection_live_status(
        last_heartbeat_at=last_heartbeat_at,
        now=now,
    )

    if connection_status == "DISCONNECTED":
        return "DISCONNECTED"

    return resolve_position_live_status(
        connection_status="LIVE",
        snapshot_at=last_position_snapshot_at,
        now=now,
    )


def resolve_connection_live_status(
    *,
    last_heartbeat_at: datetime | None,
    now: datetime | None = None,
) -> LiveDataStatus:
    current = now or datetime.now(UTC)

    if last_heartbeat_at is None:
        return "DISCONNECTED"

    if last_heartbeat_at.tzinfo is None:
        last_heartbeat_at = last_heartbeat_at.replace(tzinfo=UTC)

    heartbeat_age_ms = (current - last_heartbeat_at).total_seconds() * 1000

    if heartbeat_age_ms > HEARTBEAT_DISCONNECTED_MS:
        return "DISCONNECTED"

    return "LIVE"


def resolve_position_live_status(
    *,
    connection_status: LiveDataStatus,
    snapshot_at: datetime | None,
    now: datetime | None = None,
) -> LiveDataStatus:
    if connection_status == "DISCONNECTED":
        return "DISCONNECTED"

    if connection_status == "STALE":
        return "STALE"

    if snapshot_at is None:
        return "STALE"

    current = now or datetime.now(UTC)

    if snapshot_at.tzinfo is None:
        snapshot_at = snapshot_at.replace(tzinfo=UTC)

    snapshot_age_ms = (current - snapshot_at).total_seconds() * 1000

    if snapshot_age_ms > SNAPSHOT_STALE_MS:
        return "STALE"

    return "LIVE"
