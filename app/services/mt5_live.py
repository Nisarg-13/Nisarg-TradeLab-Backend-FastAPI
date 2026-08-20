from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies.database import DbSession
from app.models.enums import MT5ConnectionStatus, TradeDirection, TradeEventType, TradeSource, TradeStatus
from app.models.models import (
    MT5Connection,
    Mt5PositionSnapshot,
    Mt5SyncEvent,
    Trade,
    TradeEvent,
)
from app.schemas.mt5 import Mt5PositionInput, Mt5ReconcileInput, Mt5TradeEventInput
from app.services.mt5_sync import Mt5SyncService, Mt5SyncServiceDep
from app.utils.ids import generate_cuid
from app.utils.mt5_live_status import LiveDataStatus, resolve_connection_live_status


class Mt5LiveService:
    def __init__(self, db: AsyncSession, mt5_sync_service: Mt5SyncService) -> None:
        self._db = db
        self._mt5_sync_service = mt5_sync_service

    def get_connection_live_status(self, connection: MT5Connection) -> LiveDataStatus:
        return resolve_connection_live_status(
            last_heartbeat_at=connection.last_heartbeat_at
        )

    async def sync_positions(
        self, connection: MT5Connection, positions: list[Mt5PositionInput]
    ) -> dict[str, object]:
        synced_position_ids: list[str] = []

        for position in positions:
            await self._upsert_position_snapshot(connection, position)
            synced_position_ids.append(position.position_id)

        latest_snapshot_at = (
            max(position.snapshot_at for position in positions)
            if positions
            else datetime.now(UTC)
        )

        connection.last_position_snapshot_at = latest_snapshot_at
        connection.last_synced_at = datetime.now(UTC)
        connection.status = MT5ConnectionStatus.CONNECTED
        await self._db.commit()

        await self._record_sync_event(
            connection.id,
            {
                "eventType": "POSITION_SNAPSHOT",
                "payload": {"count": len(positions)},
                "occurredAt": latest_snapshot_at,
            },
        )

        return {
            "synced": len(positions),
            "positionIds": synced_position_ids,
        }

    async def process_events(
        self, connection: MT5Connection, events: list[Mt5TradeEventInput]
    ) -> dict[str, int]:
        processed = 0
        skipped = 0

        for event in events:
            existing = await self._db.execute(
                select(Mt5SyncEvent).where(
                    Mt5SyncEvent.mt5_connection_id == connection.id,
                    Mt5SyncEvent.external_event_id == event.event_id,
                )
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            await self._apply_trade_event(connection, event)
            processed += 1

        connection.last_synced_at = datetime.now(UTC)
        connection.status = MT5ConnectionStatus.CONNECTED
        await self._db.commit()

        return {"processed": processed, "skipped": skipped, "total": len(events)}

    async def reconcile(
        self, connection: MT5Connection, input_data: Mt5ReconcileInput
    ) -> dict[str, object]:
        if input_data.instruments:
            await self._mt5_sync_service.sync_instruments(
                connection, input_data.instruments
            )

        if input_data.deals:
            await self._mt5_sync_service.import_deals(connection, input_data.deals)

        position_result = await self.sync_positions(connection, input_data.positions)

        await self._record_sync_event(
            connection.id,
            {
                "eventType": "RECONCILE",
                "externalEventId": f"reconcile-{int(datetime.now(UTC).timestamp() * 1000)}",
                "payload": {
                    "since": (
                        input_data.since.astimezone(UTC).isoformat()
                        if input_data.since
                        else None
                    ),
                    "deals": len(input_data.deals),
                    "positions": len(input_data.positions),
                },
                "occurredAt": datetime.now(UTC),
            },
        )

        return {
            "reconciled": True,
            "dealsImported": len(input_data.deals),
            "positionsSynced": position_result["synced"],
        }

    async def _find_open_trade_for_position(
        self, connection: MT5Connection, position: Mt5PositionInput
    ) -> Trade | None:
        result = await self._db.execute(
            select(Trade).where(
                Trade.trading_account_id == connection.trading_account_id,
                Trade.external_position_id == position.position_id,
                Trade.source == TradeSource.MT5,
                Trade.status == TradeStatus.OPEN,
            )
        )
        trade = result.scalar_one_or_none()
        if trade is not None:
            return trade

        opened_at = position.opened_at
        if opened_at.tzinfo is None:
            opened_at = opened_at.replace(tzinfo=UTC)

        result = await self._db.execute(
            select(Trade).where(
                Trade.trading_account_id == connection.trading_account_id,
                Trade.source == TradeSource.MT5,
                Trade.status == TradeStatus.OPEN,
                Trade.symbol == position.symbol.upper(),
                Trade.opened_at >= opened_at - timedelta(seconds=2),
                Trade.opened_at <= opened_at + timedelta(seconds=2),
            )
        )
        trade = result.scalar_one_or_none()
        if trade is None:
            return None

        if not trade.external_position_id:
            trade.external_position_id = position.position_id

        return trade

    async def _upsert_position_snapshot(
        self, connection: MT5Connection, position: Mt5PositionInput
    ) -> str:
        trade = await self._find_open_trade_for_position(connection, position)

        if trade is None:
            trade = Trade(
                id=generate_cuid(),
                user_id=connection.user_id,
                trading_account_id=connection.trading_account_id,
                source=TradeSource.MT5,
                external_position_id=position.position_id,
                symbol=position.symbol.upper(),
                asset_class=position.asset_class,
                direction=TradeDirection(position.direction),
                status=TradeStatus.OPEN,
                opened_at=position.opened_at,
                average_entry_price=Decimal(str(position.open_price)),
                initial_volume=Decimal(str(position.volume)),
                current_volume=Decimal(str(position.volume)),
                swap=Decimal(str(position.swap)),
            )
            if position.stop_loss is not None:
                trade.initial_stop_loss = Decimal(str(position.stop_loss))
                trade.current_stop_loss = Decimal(str(position.stop_loss))
            if position.take_profit is not None:
                trade.initial_take_profit = Decimal(str(position.take_profit))
                trade.current_take_profit = Decimal(str(position.take_profit))

            self._db.add(trade)
            await self._db.flush()
            self._db.add(
                TradeEvent(
                    id=generate_cuid(),
                    trade_id=trade.id,
                    type=TradeEventType.OPENED,
                    new_value=(
                        f"{position.direction} {position.volume} @ {position.open_price}"
                    ),
                    occurred_at=position.opened_at,
                )
            )
        else:
            trade.current_volume = Decimal(str(position.volume))
            trade.swap = Decimal(str(position.swap))
            if position.stop_loss is not None:
                trade.current_stop_loss = (
                    Decimal(str(position.stop_loss))
                    if position.stop_loss > 0
                    else None
                )
            if position.take_profit is not None:
                trade.current_take_profit = (
                    Decimal(str(position.take_profit))
                    if position.take_profit > 0
                    else None
                )

        snapshot_result = await self._db.execute(
            select(Mt5PositionSnapshot).where(
                Mt5PositionSnapshot.mt5_connection_id == connection.id,
                Mt5PositionSnapshot.external_position_id == position.position_id,
            )
        )
        snapshot = snapshot_result.scalar_one_or_none()

        snapshot_data = {
            "trade_id": trade.id,
            "symbol": position.symbol.upper(),
            "direction": position.direction,
            "volume": Decimal(str(position.volume)),
            "open_price": Decimal(str(position.open_price)),
            "current_price": Decimal(str(position.current_price)),
            "stop_loss": (
                Decimal(str(position.stop_loss))
                if position.stop_loss is not None
                else None
            ),
            "take_profit": (
                Decimal(str(position.take_profit))
                if position.take_profit is not None
                else None
            ),
            "floating_pnl": Decimal(str(position.floating_pnl)),
            "swap": Decimal(str(position.swap)),
            "opened_at": position.opened_at,
            "snapshot_at": position.snapshot_at,
        }

        if snapshot is None:
            self._db.add(
                Mt5PositionSnapshot(
                    id=generate_cuid(),
                    mt5_connection_id=connection.id,
                    external_position_id=position.position_id,
                    **snapshot_data,
                )
            )
        else:
            for key, value in snapshot_data.items():
                setattr(snapshot, key, value)

        await self._db.flush()
        return trade.id

    async def _apply_trade_event(
        self, connection: MT5Connection, event: Mt5TradeEventInput
    ) -> None:
        if event.deal:
            await self._mt5_sync_service.import_deals(connection, [event.deal])

        result = await self._db.execute(
            select(Trade)
            .where(
                Trade.trading_account_id == connection.trading_account_id,
                Trade.external_position_id == event.position_id,
                Trade.source == TradeSource.MT5,
            )
            .order_by(Trade.opened_at.desc())
        )
        trade = result.scalars().first()

        if trade and trade.status == TradeStatus.OPEN:
            events: list[TradeEvent] = []

            if event.event_type == "SL_CHANGED" and event.stop_loss is not None:
                previous = (
                    str(trade.current_stop_loss)
                    if trade.current_stop_loss is not None
                    else None
                )
                trade.current_stop_loss = Decimal(str(event.stop_loss))
                events.append(
                    TradeEvent(
                        id=generate_cuid(),
                        trade_id=trade.id,
                        type=TradeEventType.SL_CHANGED,
                        previous_value=previous,
                        new_value=str(event.stop_loss),
                        occurred_at=event.occurred_at,
                    )
                )

            if event.event_type == "TP_CHANGED" and event.take_profit is not None:
                previous = (
                    str(trade.current_take_profit)
                    if trade.current_take_profit is not None
                    else None
                )
                trade.current_take_profit = Decimal(str(event.take_profit))
                events.append(
                    TradeEvent(
                        id=generate_cuid(),
                        trade_id=trade.id,
                        type=TradeEventType.TP_CHANGED,
                        previous_value=previous,
                        new_value=str(event.take_profit),
                        occurred_at=event.occurred_at,
                    )
                )

            if event.event_type in {"VOLUME_CHANGED", "PARTIAL_CLOSE"} and event.volume is not None:
                events.append(
                    TradeEvent(
                        id=generate_cuid(),
                        trade_id=trade.id,
                        type=(
                            TradeEventType.PARTIAL_CLOSE
                            if event.event_type == "PARTIAL_CLOSE"
                            else TradeEventType.VOLUME_CHANGED
                        ),
                        previous_value=str(trade.current_volume),
                        new_value=str(event.volume),
                        occurred_at=event.occurred_at,
                    )
                )
                trade.current_volume = Decimal(str(event.volume))

            for trade_event in events:
                self._db.add(trade_event)

        await self._record_sync_event(
            connection.id,
            {
                "eventType": event.event_type,
                "externalEventId": event.event_id,
                "externalPositionId": event.position_id,
                "payload": event.model_dump(by_alias=True, mode="json"),
                "occurredAt": event.occurred_at,
            },
        )

    async def _record_sync_event(
        self, mt5_connection_id: str, input_data: dict[str, Any]
    ) -> Mt5SyncEvent | None:
        external_event_id = input_data.get("externalEventId")
        if external_event_id:
            existing = await self._db.execute(
                select(Mt5SyncEvent).where(
                    Mt5SyncEvent.mt5_connection_id == mt5_connection_id,
                    Mt5SyncEvent.external_event_id == external_event_id,
                )
            )
            found = existing.scalar_one_or_none()
            if found:
                return found

        event = Mt5SyncEvent(
            id=generate_cuid(),
            mt5_connection_id=mt5_connection_id,
            external_event_id=external_event_id,
            event_type=input_data["eventType"],
            external_position_id=input_data.get("externalPositionId"),
            payload=input_data["payload"],
            occurred_at=input_data["occurredAt"],
        )
        self._db.add(event)
        await self._db.flush()
        return event


async def get_mt5_live_service(
    db: DbSession,
    mt5_sync_service: Mt5SyncServiceDep,
) -> Mt5LiveService:
    return Mt5LiveService(db, mt5_sync_service)


Mt5LiveServiceDep = Annotated[Mt5LiveService, Depends(get_mt5_live_service)]
