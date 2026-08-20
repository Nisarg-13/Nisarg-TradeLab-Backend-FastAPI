from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies.database import DbSession
from app.models.enums import TradeStatus
from app.models.models import MT5Connection, Mt5PositionSnapshot, Trade
from app.services.accounts import AccountsService, AccountsServiceDep
from app.utils.decimal_format import format_decimal
from app.utils.mt5_live_status import (
    LiveDataStatus,
    resolve_live_data_status,
    resolve_position_live_status,
)

_VOLUME_MATCH_TOLERANCE = Decimal("0.0001")


def _volumes_close(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) <= _VOLUME_MATCH_TOLERANCE


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).isoformat()
    return value.astimezone(UTC).isoformat()


def _resolve_snapshot_for_trade(
    trade: Trade,
    snapshot_by_trade_id: dict[str, Mt5PositionSnapshot],
    snapshot_by_external_id: dict[str, Mt5PositionSnapshot],
    snapshots: list[Mt5PositionSnapshot],
) -> Mt5PositionSnapshot | None:
    snapshot = snapshot_by_trade_id.get(trade.id)
    if snapshot is not None:
        return snapshot

    if trade.external_position_id:
        snapshot = snapshot_by_external_id.get(trade.external_position_id)
        if snapshot is not None:
            return snapshot

    for candidate in snapshots:
        if candidate.symbol != trade.symbol:
            continue
        if candidate.direction.value != trade.direction.value:
            continue
        if not _volumes_close(candidate.volume, trade.current_volume):
            continue
        return candidate

    return None


class LiveTradesService:
    def __init__(self, db: AsyncSession, accounts_service: AccountsService) -> None:
        self._db = db
        self._accounts_service = accounts_service

    async def get_live_trades_for_user(
        self, user_id: str, query: dict[str, str | None]
    ) -> dict[str, object]:
        trading_account_id = query.get("tradingAccountId")

        if trading_account_id:
            await self._accounts_service.find_by_id_for_user(trading_account_id, user_id)

        connection_query = select(MT5Connection).where(MT5Connection.user_id == user_id)
        if trading_account_id:
            connection_query = connection_query.where(
                MT5Connection.trading_account_id == trading_account_id
            )

        connection_result = await self._db.execute(
            connection_query.options(selectinload(MT5Connection.trading_account))
        )
        connections = connection_result.scalars().all()

        trade_query = select(Trade).where(
            Trade.user_id == user_id,
            Trade.status == TradeStatus.OPEN,
        )
        if trading_account_id:
            trade_query = trade_query.where(Trade.trading_account_id == trading_account_id)

        trade_result = await self._db.execute(
            trade_query.options(selectinload(Trade.trading_account)).order_by(
                Trade.opened_at.desc()
            ).limit(100)
        )
        open_trades = trade_result.scalars().all()

        connection_ids = [connection.id for connection in connections]

        if connection_ids:
            snapshot_result = await self._db.execute(
                select(Mt5PositionSnapshot)
                .where(Mt5PositionSnapshot.mt5_connection_id.in_(connection_ids))
                .order_by(Mt5PositionSnapshot.snapshot_at.desc())
            )
            snapshots = snapshot_result.scalars().all()
        else:
            snapshots = []
        snapshot_by_trade_id: dict[str, Mt5PositionSnapshot] = {}
        snapshot_by_external_id: dict[str, Mt5PositionSnapshot] = {}
        for snapshot in snapshots:
            if snapshot.trade_id and snapshot.trade_id not in snapshot_by_trade_id:
                snapshot_by_trade_id[snapshot.trade_id] = snapshot
            if snapshot.external_position_id not in snapshot_by_external_id:
                snapshot_by_external_id[snapshot.external_position_id] = snapshot

        connection_by_account_id = {
            connection.trading_account_id: connection for connection in connections
        }

        connection_statuses = [
            {
                "connectionId": connection.id,
                "tradingAccountId": connection.trading_account_id,
                "tradingAccountName": connection.trading_account.name,
                "mt5Login": connection.mt5_login,
                "serverName": connection.server_name,
                "connectionStatus": connection.status.value,
                "liveStatus": resolve_live_data_status(
                    last_heartbeat_at=connection.last_heartbeat_at,
                    last_position_snapshot_at=connection.last_position_snapshot_at,
                ),
                "lastHeartbeatAt": (
                    _format_datetime(connection.last_heartbeat_at)
                    if connection.last_heartbeat_at
                    else None
                ),
                "lastSnapshotAt": (
                    _format_datetime(connection.last_position_snapshot_at)
                    if connection.last_position_snapshot_at
                    else None
                ),
            }
            for connection in connections
        ]

        positions = []
        for trade in open_trades:
            connection = connection_by_account_id.get(trade.trading_account_id)
            account_snapshots = (
                [
                    snapshot
                    for snapshot in snapshots
                    if snapshot.mt5_connection_id == connection.id
                ]
                if connection
                else []
            )
            snapshot = _resolve_snapshot_for_trade(
                trade,
                snapshot_by_trade_id,
                snapshot_by_external_id,
                account_snapshots,
            )
            connection_live_status: LiveDataStatus = (
                resolve_live_data_status(
                    last_heartbeat_at=connection.last_heartbeat_at,
                    last_position_snapshot_at=connection.last_position_snapshot_at,
                )
                if connection
                else "DISCONNECTED"
            )
            live_status = (
                resolve_position_live_status(
                    connection_status=connection_live_status,
                    snapshot_at=snapshot.snapshot_at if snapshot else None,
                )
                if trade.source.value == "MT5"
                else "LIVE"
            )

            stop_loss = (
                snapshot.stop_loss
                if snapshot and snapshot.stop_loss is not None
                else trade.current_stop_loss
            )
            take_profit = (
                snapshot.take_profit
                if snapshot and snapshot.take_profit is not None
                else trade.current_take_profit
            )

            positions.append(
                {
                    "id": trade.id,
                    "tradingAccountId": trade.trading_account_id,
                    "tradingAccount": {
                        "id": trade.trading_account.id,
                        "name": trade.trading_account.name,
                        "currency": trade.trading_account.currency,
                    },
                    "source": trade.source.value,
                    "symbol": trade.symbol,
                    "direction": trade.direction.value,
                    "status": trade.status.value,
                    "averageEntryPrice": format_decimal(trade.average_entry_price),
                    "currentPrice": (
                        format_decimal(snapshot.current_price) if snapshot else None
                    ),
                    "currentStopLoss": format_decimal(stop_loss),
                    "currentTakeProfit": format_decimal(take_profit),
                    "currentVolume": format_decimal(trade.current_volume),
                    "initialRiskAmount": (
                        str(trade.initial_risk_amount)
                        if trade.initial_risk_amount is not None
                        else None
                    ),
                    "floatingPnl": (
                        str(snapshot.floating_pnl) if snapshot else None
                    ),
                    "currentR": self._calculate_current_r(
                        trade.initial_risk_amount,
                        snapshot.floating_pnl if snapshot else None,
                    ),
                    "openedAt": _format_datetime(trade.opened_at),
                    "lastSyncedAt": (
                        _format_datetime(snapshot.snapshot_at) if snapshot else None
                    ),
                    "liveStatus": live_status,
                }
            )

        aggregate_live_status = self._resolve_aggregate_live_status(
            [item["liveStatus"] for item in connection_statuses],
            [item["liveStatus"] for item in positions],
        )

        return {
            "liveStatus": aggregate_live_status,
            "connections": connection_statuses,
            "positions": positions,
        }

    @staticmethod
    def _calculate_current_r(initial_risk_amount, floating_pnl) -> str | None:
        if initial_risk_amount is None or floating_pnl is None:
            return None

        risk = float(initial_risk_amount)
        if risk <= 0:
            return None

        return f"{float(floating_pnl) / risk:.4f}"

    @staticmethod
    def _resolve_aggregate_live_status(
        connection_statuses: list[LiveDataStatus],
        position_statuses: list[LiveDataStatus],
    ) -> LiveDataStatus:
        statuses = [*connection_statuses, *position_statuses]

        if not statuses:
            return "DISCONNECTED"

        if all(status == "DISCONNECTED" for status in statuses):
            return "DISCONNECTED"

        if any(status == "LIVE" for status in statuses):
            return "LIVE"

        return "STALE"


async def get_live_trades_service(
    db: DbSession,
    accounts_service: AccountsServiceDep,
) -> LiveTradesService:
    return LiveTradesService(db, accounts_service)


LiveTradesServiceDep = Annotated[LiveTradesService, Depends(get_live_trades_service)]
