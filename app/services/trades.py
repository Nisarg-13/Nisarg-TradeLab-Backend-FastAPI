from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.calculators.trades.trade_pnl import calculate_execution_profit
from app.calculators.trades.trade_state import recalculate_trade_state
from app.models.enums import ExecutionType, TradeEventType, TradeStatus
from app.models.models import (
    InstrumentSpec,
    Mistake,
    Strategy,
    Tag,
    Trade,
    TradeEvent,
    TradeExecution,
    TradeMistake,
    TradeReview,
    TradeStrategy,
    TradeTag,
)
from app.schemas.trade import (
    AddExecutionInput,
    BulkUpdateTradeJournalInput,
    CloseTradeInput,
    CreateTradeInput,
    ListTradesQuery,
    UpdateTradeInput,
    UpdateTradeReviewInput,
)
from app.services.accounts import AccountsService
from app.services.instruments import InstrumentsService
from app.utils.decimal_format import format_decimal
from app.utils.ids import generate_cuid
from app.utils.ownership import assert_resource_ownership

TRADE_LOAD_OPTIONS = (
    selectinload(Trade.trading_account),
    selectinload(Trade.trade_strategies).selectinload(TradeStrategy.strategy),
    selectinload(Trade.trade_tags).selectinload(TradeTag.tag),
    selectinload(Trade.trade_mistakes).selectinload(TradeMistake.mistake),
    selectinload(Trade.executions),
    selectinload(Trade.events),
    selectinload(Trade.review),
)


class TradesService:
    def __init__(
        self,
        db: AsyncSession,
        accounts_service: AccountsService,
        instruments_service: InstrumentsService,
    ) -> None:
        self._db = db
        self._accounts_service = accounts_service
        self._instruments_service = instruments_service

    async def list_for_user(self, user_id: str, query: ListTradesQuery) -> dict[str, Any]:
        page = query.page or 1
        limit = query.limit or 10
        skip = (page - 1) * limit

        filters = [Trade.user_id == user_id]
        if query.trading_account_id:
            filters.append(Trade.trading_account_id == query.trading_account_id)
        if query.symbol:
            filters.append(Trade.symbol == query.symbol.upper())
        if query.status:
            filters.append(Trade.status == query.status)
        if query.direction:
            filters.append(Trade.direction == query.direction)
        if query.opened_from:
            filters.append(Trade.opened_at >= query.opened_from)
        if query.opened_to:
            filters.append(Trade.opened_at <= query.opened_to)

        order_by = self._resolve_sort(query.sort)

        total_result = await self._db.execute(
            select(func.count()).select_from(Trade).where(*filters)
        )
        total = total_result.scalar_one()

        result = await self._db.execute(
            select(Trade)
            .options(*TRADE_LOAD_OPTIONS)
            .where(*filters)
            .order_by(order_by)
            .offset(skip)
            .limit(limit)
        )
        trades = result.scalars().unique().all()

        return {
            "data": [self.to_trade_response(trade) for trade in trades],
            "meta": {
                "page": page,
                "limit": limit,
                "total": total,
                "totalPages": max((total + limit - 1) // limit, 1),
            },
        }

    async def find_by_id_for_user(self, trade_id: str, user_id: str) -> Trade:
        result = await self._db.execute(
            select(Trade).options(*TRADE_LOAD_OPTIONS).where(Trade.id == trade_id)
        )
        trade = result.scalar_one_or_none()

        if not trade:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trade not found",
            )

        assert_resource_ownership(trade.user_id, user_id)
        return trade

    async def create_for_user(self, user_id: str, input_data: CreateTradeInput) -> Trade:
        account = await self._accounts_service.find_by_id_for_user(
            input_data.trading_account_id,
            user_id,
        )
        instrument = await self._get_instrument_spec(
            input_data.trading_account_id,
            input_data.symbol,
            user_id,
        )

        await self._validate_strategies(user_id, input_data.strategy_ids)
        await self._validate_tags(user_id, input_data.tag_ids)
        await self._validate_mistakes(user_id, input_data.mistake_ids)

        executed_at = input_data.executed_at or datetime.now(UTC)
        trade_id = generate_cuid()

        trade = Trade(
            id=trade_id,
            user_id=user_id,
            trading_account_id=input_data.trading_account_id,
            symbol=instrument.symbol,
            asset_class=instrument.asset_class,
            direction=input_data.direction,
            status=TradeStatus.OPEN,
            opened_at=executed_at,
            average_entry_price=Decimal(str(input_data.entry_price)),
            initial_volume=Decimal(str(input_data.volume)),
            current_volume=Decimal(str(input_data.volume)),
            initial_stop_loss=(
                Decimal(str(input_data.stop_loss))
                if input_data.stop_loss is not None
                else None
            ),
            current_stop_loss=(
                Decimal(str(input_data.stop_loss))
                if input_data.stop_loss is not None
                else None
            ),
            initial_take_profit=(
                Decimal(str(input_data.take_profit))
                if input_data.take_profit is not None
                else None
            ),
            current_take_profit=(
                Decimal(str(input_data.take_profit))
                if input_data.take_profit is not None
                else None
            ),
            account_balance_at_entry=(
                Decimal(str(input_data.account_balance_at_entry))
                if input_data.account_balance_at_entry is not None
                else account.current_balance
            ),
            initial_risk_amount=(
                Decimal(str(input_data.initial_risk_amount))
                if input_data.initial_risk_amount is not None
                else None
            ),
            initial_risk_percentage=(
                Decimal(str(input_data.initial_risk_percentage))
                if input_data.initial_risk_percentage is not None
                else None
            ),
            planned_rr=(
                Decimal(str(input_data.planned_rr))
                if input_data.planned_rr is not None
                else None
            ),
        )
        self._db.add(trade)

        self._db.add(
            TradeExecution(
                id=generate_cuid(),
                trade_id=trade_id,
                type=ExecutionType.ENTRY,
                price=Decimal(str(input_data.entry_price)),
                volume=Decimal(str(input_data.volume)),
                executed_at=executed_at,
            )
        )

        self._db.add(
            TradeEvent(
                id=generate_cuid(),
                trade_id=trade_id,
                type=TradeEventType.OPENED,
                new_value=f"{input_data.direction.value} {input_data.volume} @ {input_data.entry_price}",
                occurred_at=executed_at,
            )
        )

        if input_data.review:
            self._db.add(
                TradeReview(
                    id=generate_cuid(),
                    trade_id=trade_id,
                    **self._review_data(input_data.review),
                )
            )

        await self._sync_associations(
            trade_id,
            input_data.strategy_ids,
            input_data.tag_ids,
            input_data.mistake_ids,
        )
        await self._db.commit()

        return await self.find_by_id_for_user(trade_id, user_id)

    async def update_for_user(
        self,
        trade_id: str,
        user_id: str,
        input_data: UpdateTradeInput,
    ) -> Trade:
        trade = await self.find_by_id_for_user(trade_id, user_id)
        is_closed = trade.status == TradeStatus.CLOSED

        if is_closed:
            update_input = input_data.model_copy(
                update={"current_stop_loss": None, "current_take_profit": None}
            )
        else:
            update_input = input_data

        await self._validate_strategies(user_id, update_input.strategy_ids)
        await self._validate_tags(user_id, update_input.tag_ids)
        await self._validate_mistakes(user_id, update_input.mistake_ids)

        events: list[TradeEvent] = []
        now = datetime.now(UTC)

        if not is_closed and update_input.current_stop_loss is not None:
            previous = str(trade.current_stop_loss) if trade.current_stop_loss else None
            next_value = (
                None
                if update_input.current_stop_loss is None
                else str(update_input.current_stop_loss)
            )
            if previous != next_value:
                events.append(
                    TradeEvent(
                        id=generate_cuid(),
                        trade_id=trade_id,
                        type=TradeEventType.SL_CHANGED,
                        previous_value=previous,
                        new_value=next_value,
                        occurred_at=now,
                    )
                )
            trade.current_stop_loss = (
                None
                if update_input.current_stop_loss is None
                else Decimal(str(update_input.current_stop_loss))
            )

        if not is_closed and update_input.current_take_profit is not None:
            previous = str(trade.current_take_profit) if trade.current_take_profit else None
            next_value = (
                None
                if update_input.current_take_profit is None
                else str(update_input.current_take_profit)
            )
            if previous != next_value:
                events.append(
                    TradeEvent(
                        id=generate_cuid(),
                        trade_id=trade_id,
                        type=TradeEventType.TP_CHANGED,
                        previous_value=previous,
                        new_value=next_value,
                        occurred_at=now,
                    )
                )
            trade.current_take_profit = (
                None
                if update_input.current_take_profit is None
                else Decimal(str(update_input.current_take_profit))
            )

        if update_input.chart_timeframe is not None:
            trade.chart_timeframe = update_input.chart_timeframe

        for event in events:
            self._db.add(event)

        if update_input.review:
            await self._apply_review(trade_id, update_input.review)

        await self._sync_associations(
            trade_id,
            update_input.strategy_ids,
            update_input.tag_ids,
            update_input.mistake_ids,
        )
        await self._db.commit()

        return await self.find_by_id_for_user(trade_id, user_id)

    async def bulk_update_journal_for_user(
        self,
        user_id: str,
        input_data: BulkUpdateTradeJournalInput,
    ) -> dict[str, Any]:
        update_payload = UpdateTradeInput(
            chart_timeframe=input_data.chart_timeframe,
            strategy_ids=input_data.strategy_ids,
            tag_ids=input_data.tag_ids,
            mistake_ids=input_data.mistake_ids,
            review=input_data.review,
        )

        await self._validate_strategies(user_id, update_payload.strategy_ids)
        await self._validate_tags(user_id, update_payload.tag_ids)
        await self._validate_mistakes(user_id, update_payload.mistake_ids)

        updated_ids: list[str] = []
        for trade_id in input_data.trade_ids:
            trade = await self.find_by_id_for_user(trade_id, user_id)

            if update_payload.chart_timeframe is not None:
                trade.chart_timeframe = update_payload.chart_timeframe

            if update_payload.review:
                await self._apply_review(trade_id, update_payload.review)

            await self._sync_associations(
                trade_id,
                update_payload.strategy_ids,
                update_payload.tag_ids,
                update_payload.mistake_ids,
            )
            updated_ids.append(trade_id)

        await self._db.commit()

        updated_trades = []
        for trade_id in updated_ids:
            trade = await self.find_by_id_for_user(trade_id, user_id)
            updated_trades.append(self.to_trade_response(trade))

        return {
            "data": updated_trades,
            "meta": {"updated": len(updated_trades)},
        }

    async def add_execution_for_user(
        self,
        trade_id: str,
        user_id: str,
        input_data: AddExecutionInput,
    ) -> Trade:
        trade = await self.find_by_id_for_user(trade_id, user_id)

        if trade.status == TradeStatus.CLOSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Closed trades cannot be modified.",
            )

        instrument = await self._get_instrument_spec(
            trade.trading_account_id,
            trade.symbol,
            user_id,
        )
        executed_at = input_data.executed_at or datetime.now(UTC)

        if (
            input_data.type == ExecutionType.EXIT
            and input_data.volume > float(trade.current_volume)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Exit volume exceeds the remaining open volume.",
            )

        pricing = self._to_instrument_pricing(instrument)

        profit = (
            calculate_execution_profit(
                trade.direction.value,
                float(trade.average_entry_price),
                input_data.price,
                input_data.volume,
                pricing,
            )
            if input_data.type == ExecutionType.EXIT
            else 0
        )

        self._db.add(
            TradeExecution(
                id=generate_cuid(),
                trade_id=trade_id,
                type=input_data.type,
                price=Decimal(str(input_data.price)),
                volume=Decimal(str(input_data.volume)),
                profit=Decimal(str(profit)),
                commission=Decimal(str(input_data.commission or 0)),
                swap=Decimal(str(input_data.swap or 0)),
                fee=Decimal(str(input_data.fee or 0)),
                executed_at=executed_at,
            )
        )
        await self._db.flush()

        exec_result = await self._db.execute(
            select(TradeExecution)
            .where(TradeExecution.trade_id == trade_id)
            .order_by(TradeExecution.executed_at.asc())
        )
        executions = exec_result.scalars().all()

        state = recalculate_trade_state(
            {
                "direction": trade.direction.value,
                "initialRiskAmount": (
                    float(trade.initial_risk_amount)
                    if trade.initial_risk_amount is not None
                    else None
                ),
                "instrument": pricing,
                "executions": [
                    {
                        "type": execution.type.value,
                        "price": float(execution.price),
                        "volume": float(execution.volume),
                        "profit": (
                            float(execution.profit)
                            if execution.type == ExecutionType.EXIT
                            else None
                        ),
                        "commission": float(execution.commission),
                        "swap": float(execution.swap),
                        "fee": float(execution.fee),
                        "executedAt": execution.executed_at,
                    }
                    for execution in executions
                ],
            }
        )

        trade.average_entry_price = Decimal(str(state["averageEntryPrice"]))
        trade.average_exit_price = (
            None
            if state["averageExitPrice"] is None
            else Decimal(str(state["averageExitPrice"]))
        )
        trade.initial_volume = Decimal(str(state["initialVolume"]))
        trade.current_volume = Decimal(str(state["currentVolume"]))
        trade.gross_pnl = Decimal(str(state["grossPnl"]))
        trade.commission = Decimal(str(state["commission"]))
        trade.swap = Decimal(str(state["swap"]))
        trade.fees = Decimal(str(state["fees"]))
        trade.net_pnl = Decimal(str(state["netPnl"]))
        trade.realized_r = (
            None if state["realizedR"] is None else Decimal(str(state["realizedR"]))
        )
        trade.status = TradeStatus(state["status"])
        trade.closed_at = state["closedAt"]

        event_type = (
            TradeEventType.VOLUME_CHANGED
            if input_data.type == ExecutionType.ENTRY
            else TradeEventType.CLOSED
            if state["status"] == "CLOSED"
            else TradeEventType.PARTIAL_CLOSE
        )

        self._db.add(
            TradeEvent(
                id=generate_cuid(),
                trade_id=trade_id,
                type=event_type,
                new_value=f"{input_data.type.value} {input_data.volume} @ {input_data.price}",
                occurred_at=executed_at,
            )
        )
        await self._db.commit()

        return await self.find_by_id_for_user(trade_id, user_id)

    async def close_for_user(
        self,
        trade_id: str,
        user_id: str,
        input_data: CloseTradeInput,
    ) -> Trade:
        trade = await self.find_by_id_for_user(trade_id, user_id)

        if trade.status == TradeStatus.CLOSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trade is already closed.",
            )

        remaining_volume = float(trade.current_volume)
        if remaining_volume <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trade has no remaining volume to close.",
            )

        return await self.add_execution_for_user(
            trade_id,
            user_id,
            AddExecutionInput(
                type=ExecutionType.EXIT,
                price=input_data.price,
                volume=remaining_volume,
                commission=input_data.commission,
                swap=input_data.swap,
                fee=input_data.fee,
                executed_at=input_data.executed_at,
            ),
        )

    async def get_review_for_user(self, trade_id: str, user_id: str) -> TradeReview:
        trade = await self.find_by_id_for_user(trade_id, user_id)
        if not trade.review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trade review not found",
            )
        return trade.review

    async def update_review_for_user(
        self,
        trade_id: str,
        user_id: str,
        input_data: UpdateTradeReviewInput,
    ) -> TradeReview:
        await self.find_by_id_for_user(trade_id, user_id)
        review = await self._apply_review(trade_id, input_data)
        await self._db.commit()
        await self._db.refresh(review)
        return review

    async def _apply_review(
        self,
        trade_id: str,
        review_input: UpdateTradeReviewInput,
    ) -> TradeReview:
        result = await self._db.execute(
            select(TradeReview).where(TradeReview.trade_id == trade_id)
        )
        review = result.scalar_one_or_none()
        data = self._review_data(review_input)

        if review:
            for key, value in data.items():
                setattr(review, key, value)
            return review

        review = TradeReview(id=generate_cuid(), trade_id=trade_id, **data)
        self._db.add(review)
        return review

    def to_trade_response(self, trade: Trade) -> dict[str, Any]:
        return {
            "id": trade.id,
            "tradingAccountId": trade.trading_account_id,
            "tradingAccount": {
                "id": trade.trading_account.id,
                "name": trade.trading_account.name,
                "currency": trade.trading_account.currency,
            },
            "source": trade.source.value,
            "symbol": trade.symbol,
            "assetClass": trade.asset_class.value,
            "chartTimeframe": (
                trade.chart_timeframe.value if trade.chart_timeframe else None
            ),
            "direction": trade.direction.value,
            "status": trade.status.value,
            "openedAt": trade.opened_at.isoformat(),
            "closedAt": trade.closed_at.isoformat() if trade.closed_at else None,
            "averageEntryPrice": format_decimal(trade.average_entry_price),
            "averageExitPrice": format_decimal(trade.average_exit_price),
            "initialVolume": format_decimal(trade.initial_volume),
            "currentVolume": format_decimal(trade.current_volume),
            "initialStopLoss": format_decimal(trade.initial_stop_loss),
            "currentStopLoss": format_decimal(trade.current_stop_loss),
            "initialTakeProfit": format_decimal(trade.initial_take_profit),
            "currentTakeProfit": format_decimal(trade.current_take_profit),
            "accountBalanceAtEntry": (
                str(trade.account_balance_at_entry)
                if trade.account_balance_at_entry is not None
                else None
            ),
            "initialRiskAmount": (
                str(trade.initial_risk_amount) if trade.initial_risk_amount else None
            ),
            "initialRiskPercentage": (
                str(trade.initial_risk_percentage)
                if trade.initial_risk_percentage
                else None
            ),
            "plannedRR": str(trade.planned_rr) if trade.planned_rr else None,
            "grossPnl": str(trade.gross_pnl),
            "commission": str(trade.commission),
            "swap": str(trade.swap),
            "fees": str(trade.fees),
            "netPnl": str(trade.net_pnl),
            "realizedR": str(trade.realized_r) if trade.realized_r else None,
            "strategies": [
                {"id": row.strategy.id, "name": row.strategy.name}
                for row in trade.trade_strategies
            ],
            "tags": [{"id": row.tag.id, "name": row.tag.name} for row in trade.trade_tags],
            "mistakes": [
                {"id": row.mistake.id, "name": row.mistake.name}
                for row in trade.trade_mistakes
            ],
            "executions": [
                self._to_execution_response(execution)
                for execution in sorted(trade.executions, key=lambda row: row.executed_at)
            ],
            "events": [
                self._to_event_response(event)
                for event in sorted(trade.events, key=lambda row: row.occurred_at)
            ],
            "review": self.to_review_response(trade.review) if trade.review else None,
            "createdAt": trade.created_at.isoformat(),
            "updatedAt": trade.updated_at.isoformat(),
        }

    def to_review_response(self, review: TradeReview) -> dict[str, Any]:
        return {
            "id": review.id,
            "tradeId": review.trade_id,
            "marketBias": review.market_bias.value if review.market_bias else None,
            "preTradePlan": review.pre_trade_plan,
            "postTradePlan": review.post_trade_plan,
            "preTradeEmotion": (
                review.pre_trade_emotion.value if review.pre_trade_emotion else None
            ),
            "postTradeEmotion": (
                review.post_trade_emotion.value if review.post_trade_emotion else None
            ),
            "confidenceScore": review.confidence_score,
            "planCompliance": (
                review.plan_compliance.value if review.plan_compliance else None
            ),
            "entryReason": review.entry_reason,
            "whatWentWell": review.what_went_well,
            "whatWentWrong": review.what_went_wrong,
            "notes": review.notes,
            "lesson": review.lesson,
            "createdAt": review.created_at.isoformat(),
            "updatedAt": review.updated_at.isoformat(),
        }

    def _to_execution_response(self, execution: TradeExecution) -> dict[str, Any]:
        return {
            "id": execution.id,
            "tradeId": execution.trade_id,
            "type": execution.type.value,
            "price": format_decimal(execution.price),
            "volume": format_decimal(execution.volume),
            "profit": str(execution.profit),
            "commission": str(execution.commission),
            "swap": str(execution.swap),
            "fee": str(execution.fee),
            "executedAt": execution.executed_at.isoformat(),
        }

    def _to_event_response(self, event: TradeEvent) -> dict[str, Any]:
        return {
            "id": event.id,
            "tradeId": event.trade_id,
            "type": event.type.value,
            "previousValue": event.previous_value,
            "newValue": event.new_value,
            "occurredAt": event.occurred_at.isoformat(),
            "metadata": event.metadata_,
        }

    def _resolve_sort(self, sort: str | None):
        if sort == "openedAt_asc":
            return Trade.opened_at.asc()
        if sort == "netPnl_desc":
            return Trade.net_pnl.desc()
        if sort == "netPnl_asc":
            return Trade.net_pnl.asc()
        return Trade.opened_at.desc()

    async def _get_instrument_spec(
        self,
        account_id: str,
        symbol: str,
        user_id: str,
    ) -> InstrumentSpec:
        instruments = await self._instruments_service.list_for_account(account_id, user_id)
        instrument = next(
            (row for row in instruments if row.symbol.upper() == symbol.upper()),
            None,
        )
        if not instrument:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Instrument {symbol} is not configured for this account.",
            )
        return instrument

    def _to_instrument_pricing(self, instrument: InstrumentSpec) -> dict[str, float]:
        return {
            "contractSize": float(instrument.contract_size),
            "tickSize": float(instrument.tick_size),
            "tickValueProfit": float(instrument.tick_value_profit),
            "tickValueLoss": float(instrument.tick_value_loss),
        }

    async def _validate_strategies(self, user_id: str, strategy_ids: list[str] | None) -> None:
        if not strategy_ids:
            return

        result = await self._db.execute(
            select(Strategy).where(Strategy.id.in_(strategy_ids))
        )
        strategies = result.scalars().all()
        if len(strategies) != len(strategy_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more strategies were not found.",
            )
        for strategy in strategies:
            assert_resource_ownership(strategy.user_id, user_id)

    async def _validate_tags(self, user_id: str, tag_ids: list[str] | None) -> None:
        if not tag_ids:
            return

        result = await self._db.execute(select(Tag).where(Tag.id.in_(tag_ids)))
        tags = result.scalars().all()
        if len(tags) != len(tag_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more tags were not found.",
            )
        for tag in tags:
            assert_resource_ownership(tag.user_id, user_id)

    async def _validate_mistakes(self, user_id: str, mistake_ids: list[str] | None) -> None:
        if not mistake_ids:
            return

        result = await self._db.execute(select(Mistake).where(Mistake.id.in_(mistake_ids)))
        mistakes = result.scalars().all()
        if len(mistakes) != len(mistake_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more mistakes were not found.",
            )
        for mistake in mistakes:
            assert_resource_ownership(mistake.user_id, user_id)

    async def _sync_associations(
        self,
        trade_id: str,
        strategy_ids: list[str] | None,
        tag_ids: list[str] | None,
        mistake_ids: list[str] | None,
    ) -> None:
        if strategy_ids is not None:
            await self._db.execute(
                delete(TradeStrategy).where(TradeStrategy.trade_id == trade_id)
            )
            for strategy_id in strategy_ids:
                self._db.add(TradeStrategy(trade_id=trade_id, strategy_id=strategy_id))

        if tag_ids is not None:
            await self._db.execute(delete(TradeTag).where(TradeTag.trade_id == trade_id))
            for tag_id in tag_ids:
                self._db.add(TradeTag(trade_id=trade_id, tag_id=tag_id))

        if mistake_ids is not None:
            await self._db.execute(
                delete(TradeMistake).where(TradeMistake.trade_id == trade_id)
            )
            for mistake_id in mistake_ids:
                self._db.add(TradeMistake(trade_id=trade_id, mistake_id=mistake_id))

    def _review_data(self, review_input: UpdateTradeReviewInput) -> dict[str, Any]:
        return review_input.model_dump(exclude_unset=True, by_alias=False)
