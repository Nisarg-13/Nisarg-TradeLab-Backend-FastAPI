from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.calculators.trades.trade_state import recalculate_trade_state
from app.dependencies.database import DbSession
from app.models.enums import (
    AccountSource,
    ExecutionType,
    MT5ConnectionStatus,
    TradeEventType,
    TradeSource,
    TradeStatus,
)
from app.models.models import (
    InstrumentSpec,
    MT5Connection,
    Mt5ProcessedDeal,
    Mt5PositionSnapshot,
    Trade,
    TradeEvent,
    TradeExecution,
)
from app.schemas.mt5 import (
    Mt5AccountSnapshotInput,
    Mt5ConnectInput,
    Mt5DealInput,
    Mt5InstrumentInput,
    Mt5PositionLevelInput,
)
from app.services.mt5_connection import Mt5ConnectionService, Mt5ConnectionServiceDep
from app.utils.ids import generate_cuid

SlTpMode = Literal["fill-missing", "force"]


class Mt5SyncService:
    def __init__(
        self,
        db: AsyncSession,
        mt5_connection_service: Mt5ConnectionService,
    ) -> None:
        self._db = db
        self._mt5_connection_service = mt5_connection_service

    async def connect(
        self, connection: MT5Connection, input_data: Mt5ConnectInput
    ) -> dict[str, object]:
        await self._mt5_connection_service.assert_login_server_binding(
            connection,
            input_data.mt5_login,
            input_data.server_name,
        )

        now = datetime.now(UTC)
        connection.mt5_login = input_data.mt5_login
        connection.server_name = input_data.server_name
        connection.broker_name = input_data.broker_name
        connection.status = MT5ConnectionStatus.CONNECTED
        connection.ea_version = input_data.ea_version
        connection.last_heartbeat_at = now
        connection.last_synced_at = now

        from app.models.models import TradingAccount

        trading_account = await self._db.get(
            TradingAccount, connection.trading_account_id
        )

        if trading_account is not None:
            trading_account.source = AccountSource.MT5
            trading_account.broker_name = input_data.broker_name
            trading_account.currency = input_data.currency
            trading_account.current_balance = Decimal(str(input_data.balance))

        await self._db.commit()
        await self._db.refresh(connection)

        return {
            "connectionId": connection.id,
            "status": connection.status.value,
            "paired": True,
        }

    async def heartbeat(
        self, connection: MT5Connection, ea_version: str | None = None
    ) -> dict[str, object]:
        connection.status = MT5ConnectionStatus.CONNECTED
        connection.last_heartbeat_at = datetime.now(UTC)
        if ea_version:
            connection.ea_version = ea_version
        await self._db.commit()
        await self._db.refresh(connection)

        return {
            "connectionId": connection.id,
            "status": connection.status.value,
            "lastHeartbeatAt": (
                connection.last_heartbeat_at.astimezone(UTC).isoformat()
                if connection.last_heartbeat_at
                else None
            ),
        }

    async def sync_account_snapshot(
        self,
        connection: MT5Connection,
        input_data: Mt5AccountSnapshotInput,
    ) -> dict[str, object]:
        from app.models.models import TradingAccount

        trading_account = await self._db.get(
            TradingAccount, connection.trading_account_id
        )
        if trading_account is not None:
            trading_account.current_balance = Decimal(str(input_data.balance))
            if input_data.currency:
                trading_account.currency = input_data.currency

        connection.last_synced_at = datetime.now(UTC)
        connection.status = MT5ConnectionStatus.CONNECTED
        await self._db.commit()

        return {"synced": True, "equity": input_data.equity}

    async def sync_instruments(
        self,
        connection: MT5Connection,
        instruments: list[Mt5InstrumentInput],
    ) -> dict[str, int]:
        for instrument in instruments:
            symbol = instrument.symbol.upper()
            result = await self._db.execute(
                select(InstrumentSpec).where(
                    InstrumentSpec.trading_account_id == connection.trading_account_id,
                    InstrumentSpec.symbol == symbol,
                )
            )
            existing = result.scalar_one_or_none()
            data = {
                "description": instrument.description,
                "asset_class": instrument.asset_class,
                "digits": instrument.digits,
                "point": Decimal(str(instrument.point)),
                "tick_size": Decimal(str(instrument.tick_size)),
                "tick_value_profit": Decimal(str(instrument.tick_value_profit)),
                "tick_value_loss": Decimal(str(instrument.tick_value_loss)),
                "contract_size": Decimal(str(instrument.contract_size)),
                "volume_min": Decimal(str(instrument.volume_min)),
                "volume_max": Decimal(str(instrument.volume_max)),
                "volume_step": Decimal(str(instrument.volume_step)),
                "base_currency": instrument.base_currency,
                "profit_currency": instrument.profit_currency,
            }

            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
            else:
                self._db.add(
                    InstrumentSpec(
                        id=generate_cuid(),
                        trading_account_id=connection.trading_account_id,
                        symbol=symbol,
                        **data,
                    )
                )

        connection.last_synced_at = datetime.now(UTC)
        await self._db.commit()
        return {"imported": len(instruments)}

    async def import_deals(
        self, connection: MT5Connection, deals: list[Mt5DealInput]
    ) -> dict[str, int]:
        imported = 0
        skipped = 0

        for deal in deals:
            processed = await self._db.execute(
                select(Mt5ProcessedDeal).where(
                    Mt5ProcessedDeal.mt5_connection_id == connection.id,
                    Mt5ProcessedDeal.external_deal_id == deal.deal_id,
                )
            )
            if processed.scalar_one_or_none():
                await self._backfill_sl_tp_from_deal(connection, deal)
                skipped += 1
                continue

            existing_execution = await self._db.execute(
                select(TradeExecution)
                .join(Trade)
                .where(
                    TradeExecution.external_deal_id == deal.deal_id,
                    Trade.trading_account_id == connection.trading_account_id,
                    Trade.source == TradeSource.MT5,
                )
            )
            execution = existing_execution.scalar_one_or_none()
            if execution:
                await self._backfill_sl_tp_from_deal(connection, deal)
                self._db.add(
                    Mt5ProcessedDeal(
                        id=generate_cuid(),
                        mt5_connection_id=connection.id,
                        external_deal_id=deal.deal_id,
                        trade_id=execution.trade_id,
                        execution_id=execution.id,
                    )
                )
                skipped += 1
                continue

            if await self._import_single_deal(connection, deal):
                imported += 1

        connection.last_synced_at = datetime.now(UTC)
        connection.status = MT5ConnectionStatus.CONNECTED
        await self._db.commit()
        return {"imported": imported, "skipped": skipped, "total": len(deals)}

    async def import_position_levels(
        self,
        connection: MT5Connection,
        levels: list[Mt5PositionLevelInput],
    ) -> dict[str, int]:
        updated = 0
        skipped = 0
        not_found = 0

        for level in levels:
            if level.stop_loss is None and level.take_profit is None:
                skipped += 1
                continue

            trade = await self._find_trade_for_position_level(connection, level)
            if trade is None:
                not_found += 1
                skipped += 1
                continue

            data = self._build_sl_tp_apply_fields(level, trade, "force")
            if not trade.external_position_id:
                data["external_position_id"] = level.position_id

            if not data:
                skipped += 1
                continue

            for key, value in data.items():
                setattr(trade, key, value)
            updated += 1

        connection.last_synced_at = datetime.now(UTC)
        connection.status = MT5ConnectionStatus.CONNECTED
        await self._db.commit()
        return {
            "updated": updated,
            "skipped": skipped,
            "notFound": not_found,
            "total": len(levels),
        }

    async def repair_imported_trades(self, trading_account_id: str) -> dict[str, int]:
        normalized = await self._normalize_zero_sl_tp(trading_account_id)
        dedupe = await self.deduplicate_imported_trades(trading_account_id)
        recalculated = await self.recalculate_imported_trades(trading_account_id)
        sl_tp_backfilled = await self._backfill_sl_tp_from_snapshots(trading_account_id)
        return {**normalized, **dedupe, **recalculated, **sl_tp_backfilled}

    async def deduplicate_imported_trades(self, trading_account_id: str) -> dict[str, int]:
        result = await self._db.execute(
            select(TradeExecution)
            .join(Trade)
            .where(
                TradeExecution.external_deal_id.is_not(None),
                Trade.trading_account_id == trading_account_id,
                Trade.source == TradeSource.MT5,
            )
            .order_by(TradeExecution.executed_at.asc(), TradeExecution.id.asc())
        )
        executions = result.scalars().all()

        seen_deal_ids: set[str] = set()
        duplicate_execution_ids: list[str] = []

        for execution in executions:
            deal_id = execution.external_deal_id
            if not deal_id:
                continue
            if deal_id in seen_deal_ids:
                duplicate_execution_ids.append(execution.id)
                continue
            seen_deal_ids.add(deal_id)

        if duplicate_execution_ids:
            await self._db.execute(
                delete(TradeExecution).where(
                    TradeExecution.id.in_(duplicate_execution_ids)
                )
            )
            await self._db.commit()

        return {"removedDuplicates": len(duplicate_execution_ids)}

    async def recalculate_imported_trades(self, trading_account_id: str) -> dict[str, int]:
        result = await self._db.execute(
            select(Trade)
            .where(
                Trade.trading_account_id == trading_account_id,
                Trade.source == TradeSource.MT5,
            )
            .options(selectinload(Trade.executions))
        )
        trades = result.scalars().all()
        updated = 0

        for trade in trades:
            for execution in trade.executions:
                commission = abs(float(execution.commission))
                swap = abs(float(execution.swap))
                fee = abs(float(execution.fee))
                if (
                    commission != float(execution.commission)
                    or swap != float(execution.swap)
                    or fee != float(execution.fee)
                ):
                    execution.commission = Decimal(str(commission))
                    execution.swap = Decimal(str(swap))
                    execution.fee = Decimal(str(fee))

            instrument = await self._get_instrument_pricing(
                trading_account_id, trade.symbol
            )
            state = recalculate_trade_state(
                {
                    "direction": trade.direction,
                    "initialRiskAmount": (
                        float(trade.initial_risk_amount)
                        if trade.initial_risk_amount is not None
                        else None
                    ),
                    "instrument": instrument,
                    "executions": [
                        {
                            "type": item.type.value,
                            "price": float(item.price),
                            "volume": float(item.volume),
                            "profit": (
                                float(item.profit)
                                if item.type == ExecutionType.EXIT
                                else None
                            ),
                            "commission": float(item.commission),
                            "swap": float(item.swap),
                            "fee": float(item.fee),
                            "executedAt": item.executed_at,
                        }
                        for item in sorted(
                            trade.executions, key=lambda row: row.executed_at
                        )
                    ],
                }
            )

            normalized = self._normalize_zero_sl_tp_fields(trade)
            trade.average_entry_price = Decimal(str(state["averageEntryPrice"]))
            trade.average_exit_price = (
                Decimal(str(state["averageExitPrice"]))
                if state["averageExitPrice"] is not None
                else None
            )
            trade.initial_volume = Decimal(str(state["initialVolume"]))
            trade.current_volume = Decimal(str(state["currentVolume"]))
            trade.gross_pnl = Decimal(str(state["grossPnl"]))
            trade.commission = Decimal(str(state["commission"]))
            trade.swap = Decimal(str(state["swap"]))
            trade.fees = Decimal(str(state["fees"]))
            trade.net_pnl = Decimal(str(state["netPnl"]))
            trade.realized_r = (
                Decimal(str(state["realizedR"]))
                if state["realizedR"] is not None
                else None
            )
            trade.status = TradeStatus(state["status"])
            trade.closed_at = state["closedAt"]
            for key, value in normalized.items():
                setattr(trade, key, value)
            updated += 1

        await self._db.commit()
        return {"updated": updated, "total": len(trades)}

    async def _import_single_deal(
        self, connection: MT5Connection, deal: Mt5DealInput
    ) -> bool:
        result = await self._db.execute(
            select(Trade)
            .where(
                Trade.trading_account_id == connection.trading_account_id,
                Trade.external_position_id == deal.position_id,
                Trade.source == TradeSource.MT5,
            )
            .options(selectinload(Trade.executions))
        )
        trade = result.scalar_one_or_none()

        if trade is None and deal.entry_type == "ENTRY":
            trade = Trade(
                id=generate_cuid(),
                user_id=connection.user_id,
                trading_account_id=connection.trading_account_id,
                source=TradeSource.MT5,
                external_position_id=deal.position_id,
                symbol=deal.symbol.upper(),
                asset_class=deal.asset_class,
                direction=deal.direction,
                status=TradeStatus.OPEN,
                opened_at=deal.executed_at,
                average_entry_price=Decimal(str(deal.price)),
                initial_volume=Decimal(str(deal.volume)),
                current_volume=Decimal(str(deal.volume)),
                **self._build_sl_tp_create_fields(deal),
            )
            self._db.add(trade)
            await self._db.flush()
            self._db.add(
                TradeEvent(
                    id=generate_cuid(),
                    trade_id=trade.id,
                    type=TradeEventType.OPENED,
                    new_value=f"{deal.direction} {deal.volume} @ {deal.price}",
                    occurred_at=deal.executed_at,
                )
            )

        if trade is None:
            return False

        duplicate = await self._db.execute(
            select(TradeExecution)
            .join(Trade)
            .where(
                TradeExecution.external_deal_id == deal.deal_id,
                Trade.trading_account_id == connection.trading_account_id,
                Trade.source == TradeSource.MT5,
            )
        )
        if duplicate.scalar_one_or_none():
            return False

        execution = TradeExecution(
            id=generate_cuid(),
            trade_id=trade.id,
            external_deal_id=deal.deal_id,
            type=ExecutionType(deal.entry_type),
            price=Decimal(str(deal.price)),
            volume=Decimal(str(deal.volume)),
            profit=Decimal(str(deal.profit)),
            commission=Decimal(str(abs(deal.commission))),
            swap=Decimal(str(abs(deal.swap))),
            fee=Decimal(str(abs(deal.fee))),
            executed_at=deal.executed_at,
        )
        self._db.add(execution)
        await self._db.flush()

        exec_result = await self._db.execute(
            select(TradeExecution)
            .where(TradeExecution.trade_id == trade.id)
            .order_by(TradeExecution.executed_at.asc())
        )
        executions = exec_result.scalars().all()
        instrument = await self._get_instrument_pricing(
            connection.trading_account_id, trade.symbol
        )
        state = recalculate_trade_state(
            {
                "direction": trade.direction,
                "initialRiskAmount": (
                    float(trade.initial_risk_amount)
                    if trade.initial_risk_amount is not None
                    else None
                ),
                "instrument": instrument,
                "executions": [
                    {
                        "type": item.type.value,
                        "price": float(item.price),
                        "volume": float(item.volume),
                        "profit": (
                            float(item.profit) if item.type == ExecutionType.EXIT else None
                        ),
                        "commission": float(item.commission),
                        "swap": float(item.swap),
                        "fee": float(item.fee),
                        "executedAt": item.executed_at,
                    }
                    for item in executions
                ],
            }
        )

        sl_tp_mode: SlTpMode = (
            "force" if deal.entry_type == "EXIT" else "fill-missing"
        )
        sl_tp_fields = self._build_sl_tp_apply_fields(deal, trade, sl_tp_mode)
        trade.average_entry_price = Decimal(str(state["averageEntryPrice"]))
        trade.average_exit_price = (
            Decimal(str(state["averageExitPrice"]))
            if state["averageExitPrice"] is not None
            else None
        )
        trade.initial_volume = Decimal(str(state["initialVolume"]))
        trade.current_volume = Decimal(str(state["currentVolume"]))
        trade.gross_pnl = Decimal(str(state["grossPnl"]))
        trade.commission = Decimal(str(state["commission"]))
        trade.swap = Decimal(str(state["swap"]))
        trade.fees = Decimal(str(state["fees"]))
        trade.net_pnl = Decimal(str(state["netPnl"]))
        trade.realized_r = (
            Decimal(str(state["realizedR"])) if state["realizedR"] is not None else None
        )
        trade.status = TradeStatus(state["status"])
        trade.closed_at = state["closedAt"]
        for key, value in sl_tp_fields.items():
            setattr(trade, key, value)

        if state["status"] == "CLOSED":
            closed_event = await self._db.execute(
                select(TradeEvent).where(
                    TradeEvent.trade_id == trade.id,
                    TradeEvent.type == TradeEventType.CLOSED,
                )
            )
            if closed_event.scalar_one_or_none() is None:
                self._db.add(
                    TradeEvent(
                        id=generate_cuid(),
                        trade_id=trade.id,
                        type=TradeEventType.CLOSED,
                        occurred_at=state["closedAt"] or deal.executed_at,
                    )
                )

        self._db.add(
            Mt5ProcessedDeal(
                id=generate_cuid(),
                mt5_connection_id=connection.id,
                external_deal_id=deal.deal_id,
                trade_id=trade.id,
                execution_id=execution.id,
            )
        )
        return True

    async def _find_trade_for_position_level(
        self,
        connection: MT5Connection,
        level: Mt5PositionLevelInput,
    ) -> Trade | None:
        result = await self._db.execute(
            select(Trade).where(
                Trade.trading_account_id == connection.trading_account_id,
                Trade.external_position_id == level.position_id,
                Trade.source == TradeSource.MT5,
            )
        )
        trade = result.scalar_one_or_none()
        if trade:
            return trade

        if not level.symbol or not level.opened_at:
            return None

        opened_at = level.opened_at
        if opened_at.tzinfo is None:
            opened_at = opened_at.replace(tzinfo=UTC)

        result = await self._db.execute(
            select(Trade).where(
                Trade.trading_account_id == connection.trading_account_id,
                Trade.source == TradeSource.MT5,
                Trade.symbol == level.symbol.upper(),
                Trade.opened_at >= opened_at - timedelta(seconds=2),
                Trade.opened_at <= opened_at + timedelta(seconds=2),
            )
        )
        return result.scalar_one_or_none()

    async def _backfill_sl_tp_from_deal(
        self, connection: MT5Connection, deal: Mt5DealInput
    ) -> None:
        if deal.stop_loss is None and deal.take_profit is None:
            return

        result = await self._db.execute(
            select(Trade).where(
                Trade.trading_account_id == connection.trading_account_id,
                Trade.external_position_id == deal.position_id,
                Trade.source == TradeSource.MT5,
            )
        )
        trade = result.scalar_one_or_none()
        if trade is None:
            return

        mode: SlTpMode = "force" if deal.entry_type == "EXIT" else "fill-missing"
        data = self._build_sl_tp_apply_fields(deal, trade, mode)
        if not data:
            return

        for key, value in data.items():
            setattr(trade, key, value)

    async def _backfill_sl_tp_from_snapshots(self, trading_account_id: str) -> dict[str, int]:
        result = await self._db.execute(
            select(Trade).where(
                Trade.trading_account_id == trading_account_id,
                Trade.source == TradeSource.MT5,
                Trade.external_position_id.is_not(None),
            )
        )
        trades = result.scalars().all()
        updated = 0

        for trade in trades:
            if trade.current_stop_loss is not None and trade.current_take_profit is not None:
                continue

            snapshot_result = await self._db.execute(
                select(Mt5PositionSnapshot)
                .where(
                    Mt5PositionSnapshot.external_position_id == trade.external_position_id
                )
                .order_by(Mt5PositionSnapshot.snapshot_at.desc())
            )
            snapshot = snapshot_result.scalars().first()
            if snapshot is None:
                continue

            data: dict[str, Decimal | None] = {}
            if self._is_unset_price(trade.current_stop_loss) and not self._is_unset_price(
                snapshot.stop_loss
            ):
                data["current_stop_loss"] = snapshot.stop_loss
                if self._is_unset_price(trade.initial_stop_loss):
                    data["initial_stop_loss"] = snapshot.stop_loss
            if self._is_unset_price(trade.current_take_profit) and not self._is_unset_price(
                snapshot.take_profit
            ):
                data["current_take_profit"] = snapshot.take_profit
                if self._is_unset_price(trade.initial_take_profit):
                    data["initial_take_profit"] = snapshot.take_profit

            if not data:
                continue

            for key, value in data.items():
                setattr(trade, key, value)
            updated += 1

        await self._db.commit()
        return {"slTpBackfilled": updated}

    async def _normalize_zero_sl_tp(self, trading_account_id: str) -> dict[str, int]:
        result = await self._db.execute(
            select(Trade).where(
                Trade.trading_account_id == trading_account_id,
                Trade.source == TradeSource.MT5,
            )
        )
        trades = result.scalars().all()
        normalized = 0

        for trade in trades:
            data = self._normalize_zero_sl_tp_fields(trade)
            if not data:
                continue
            for key, value in data.items():
                setattr(trade, key, value)
            normalized += 1

        await self._db.commit()
        return {"slTpNormalized": normalized}

    async def _get_instrument_pricing(
        self, trading_account_id: str, symbol: str
    ) -> dict[str, float]:
        result = await self._db.execute(
            select(InstrumentSpec).where(
                InstrumentSpec.trading_account_id == trading_account_id,
                InstrumentSpec.symbol == symbol,
            )
        )
        instrument = result.scalar_one_or_none()
        if instrument is None:
            return {
                "contractSize": 100000,
                "tickSize": 0.00001,
                "tickValueProfit": 1,
                "tickValueLoss": 1,
            }

        return {
            "contractSize": float(instrument.contract_size),
            "tickSize": float(instrument.tick_size),
            "tickValueProfit": float(instrument.tick_value_profit),
            "tickValueLoss": float(instrument.tick_value_loss),
        }

    @staticmethod
    def _is_unset_price(value: Decimal | None) -> bool:
        if value is None:
            return True
        return float(value) <= 0

    def _build_sl_tp_apply_fields(
        self,
        levels: Mt5DealInput | Mt5PositionLevelInput,
        trade: Trade,
        mode: SlTpMode,
    ) -> dict[str, Decimal]:
        fields: dict[str, Decimal] = {}

        stop_loss = getattr(levels, "stop_loss", None)
        take_profit = getattr(levels, "take_profit", None)

        if stop_loss is not None:
            if mode == "force" or self._is_unset_price(trade.current_stop_loss):
                fields["current_stop_loss"] = Decimal(str(stop_loss))
            if mode == "force" or self._is_unset_price(trade.initial_stop_loss):
                fields["initial_stop_loss"] = Decimal(str(stop_loss))

        if take_profit is not None:
            if mode == "force" or self._is_unset_price(trade.current_take_profit):
                fields["current_take_profit"] = Decimal(str(take_profit))
            if mode == "force" or self._is_unset_price(trade.initial_take_profit):
                fields["initial_take_profit"] = Decimal(str(take_profit))

        return fields

    @staticmethod
    def _build_sl_tp_create_fields(deal: Mt5DealInput) -> dict[str, Decimal]:
        fields: dict[str, Decimal] = {}
        if deal.stop_loss is not None:
            fields["initial_stop_loss"] = Decimal(str(deal.stop_loss))
            fields["current_stop_loss"] = Decimal(str(deal.stop_loss))
        if deal.take_profit is not None:
            fields["initial_take_profit"] = Decimal(str(deal.take_profit))
            fields["current_take_profit"] = Decimal(str(deal.take_profit))
        return fields

    def _normalize_zero_sl_tp_fields(self, trade: Trade) -> dict[str, None]:
        data: dict[str, None] = {}
        if self._is_unset_price(trade.current_stop_loss) and trade.current_stop_loss is not None:
            data["current_stop_loss"] = None
        if self._is_unset_price(trade.current_take_profit) and trade.current_take_profit is not None:
            data["current_take_profit"] = None
        if self._is_unset_price(trade.initial_stop_loss) and trade.initial_stop_loss is not None:
            data["initial_stop_loss"] = None
        if self._is_unset_price(trade.initial_take_profit) and trade.initial_take_profit is not None:
            data["initial_take_profit"] = None
        return data


async def get_mt5_sync_service(
    db: DbSession,
    mt5_connection_service: Mt5ConnectionServiceDep,
) -> Mt5SyncService:
    return Mt5SyncService(db, mt5_connection_service)


Mt5SyncServiceDep = Annotated[Mt5SyncService, Depends(get_mt5_sync_service)]
