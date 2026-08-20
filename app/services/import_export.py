from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies.database import DbSession
from app.models.enums import ExecutionType, TradeEventType, TradeSource, TradeStatus
from app.models.models import Trade, TradeEvent, TradeExecution, TradeStrategy
from app.schemas.import_export import (
    CsvImportCommitInput,
    CsvImportPreviewInput,
    ExportQuery,
)
from app.services.accounts import AccountsService, AccountsServiceDep
from app.services.instruments import InstrumentsService, InstrumentsServiceDep
from app.utils.csv_parse import parse_csv
from app.utils.csv_trade_mapper import (
    MappedCsvTrade,
    build_duplicate_key,
    map_csv_trades,
    to_csv,
)
from app.utils.decimal_format import format_decimal
from app.utils.ids import generate_cuid


class ImportExportService:
    def __init__(
        self,
        db: AsyncSession,
        accounts_service: AccountsService,
        instruments_service: InstrumentsService,
    ) -> None:
        self._db = db
        self._accounts_service = accounts_service
        self._instruments_service = instruments_service

    async def preview_csv_import(
        self, user_id: str, input_data: CsvImportPreviewInput
    ) -> dict[str, object]:
        return await self._build_import_preview(user_id, input_data)

    async def commit_csv_import(
        self, user_id: str, input_data: CsvImportCommitInput
    ) -> dict[str, object]:
        preview = await self._build_import_preview(user_id, input_data)
        account = await self._accounts_service.find_by_id_for_user(
            input_data.trading_account_id, user_id
        )

        valid_rows = preview["validRows"]
        if not valid_rows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid rows available to import.",
            )

        rows_to_import = (
            [row for row in valid_rows if not row["isDuplicate"]]
            if input_data.skip_duplicates
            else valid_rows
        )

        imported_count = 0

        for row in rows_to_import:
            trade_data: MappedCsvTrade = row["trade"]
            instrument = await self._resolve_instrument(
                account.id, trade_data.symbol, user_id
            )

            trade = Trade(
                id=generate_cuid(),
                user_id=user_id,
                trading_account_id=account.id,
                source=TradeSource.CSV,
                external_position_id=trade_data.external_position_id,
                symbol=trade_data.symbol,
                asset_class=instrument.asset_class,
                direction=trade_data.direction,
                status=TradeStatus.CLOSED,
                opened_at=trade_data.opened_at,
                closed_at=trade_data.closed_at,
                average_entry_price=Decimal(str(trade_data.entry_price)),
                average_exit_price=Decimal(str(trade_data.exit_price)),
                initial_volume=Decimal(str(trade_data.volume)),
                current_volume=Decimal("0"),
                gross_pnl=Decimal(str(trade_data.net_pnl)),
                commission=Decimal(str(trade_data.commission)),
                swap=Decimal(str(trade_data.swap)),
                net_pnl=Decimal(str(trade_data.net_pnl)),
            )

            if trade_data.stop_loss is not None:
                trade.initial_stop_loss = Decimal(str(trade_data.stop_loss))
                trade.current_stop_loss = Decimal(str(trade_data.stop_loss))
            if trade_data.take_profit is not None:
                trade.initial_take_profit = Decimal(str(trade_data.take_profit))
                trade.current_take_profit = Decimal(str(trade_data.take_profit))

            self._db.add(trade)
            await self._db.flush()

            self._db.add_all(
                [
                    TradeExecution(
                        id=generate_cuid(),
                        trade_id=trade.id,
                        type=ExecutionType.ENTRY,
                        price=Decimal(str(trade_data.entry_price)),
                        volume=Decimal(str(trade_data.volume)),
                        executed_at=trade_data.opened_at,
                    ),
                    TradeExecution(
                        id=generate_cuid(),
                        trade_id=trade.id,
                        type=ExecutionType.EXIT,
                        price=Decimal(str(trade_data.exit_price)),
                        volume=Decimal(str(trade_data.volume)),
                        profit=Decimal(str(trade_data.net_pnl)),
                        commission=Decimal(str(trade_data.commission)),
                        swap=Decimal(str(trade_data.swap)),
                        executed_at=trade_data.closed_at,
                    ),
                    TradeEvent(
                        id=generate_cuid(),
                        trade_id=trade.id,
                        type=TradeEventType.OPENED,
                        new_value=(
                            f"{trade_data.direction} {trade_data.volume} @ "
                            f"{trade_data.entry_price}"
                        ),
                        occurred_at=trade_data.opened_at,
                    ),
                    TradeEvent(
                        id=generate_cuid(),
                        trade_id=trade.id,
                        type=TradeEventType.CLOSED,
                        new_value=f"{trade_data.volume} @ {trade_data.exit_price}",
                        occurred_at=trade_data.closed_at,
                    ),
                ]
            )
            imported_count += 1

        await self._db.commit()

        return {
            "importedCount": imported_count,
            "skippedDuplicateCount": len(valid_rows) - len(rows_to_import),
            "rowErrors": preview["rowErrors"],
        }

    async def export_trades_csv(
        self, user_id: str, query: ExportQuery
    ) -> dict[str, str]:
        trades = await self._load_export_trades(user_id, query)
        csv = to_csv(
            [
                "symbol",
                "direction",
                "opened_at",
                "closed_at",
                "entry_price",
                "exit_price",
                "volume",
                "net_pnl",
                "commission",
                "swap",
                "realized_r",
                "source",
                "external_position_id",
            ],
            [
                [
                    trade.symbol,
                    trade.direction.value,
                    trade.opened_at.astimezone(UTC).isoformat(),
                    trade.closed_at.astimezone(UTC).isoformat() if trade.closed_at else "",
                    format_decimal(trade.average_entry_price) or "",
                    format_decimal(trade.average_exit_price) or "",
                    str(trade.initial_volume),
                    str(trade.net_pnl),
                    str(trade.commission),
                    str(trade.swap),
                    str(trade.realized_r) if trade.realized_r is not None else "",
                    trade.source.value,
                    trade.external_position_id or "",
                ]
                for trade in trades
            ],
        )

        return {
            "fileName": "tradelab-trades.csv",
            "contentType": "text/csv",
            "csv": csv,
        }

    async def export_trades_json(
        self, user_id: str, query: ExportQuery
    ) -> dict[str, object]:
        trades = await self._load_export_trades(user_id, query)

        return {
            "exportedAt": datetime.now(UTC).isoformat(),
            "tradeCount": len(trades),
            "trades": [
                {
                    "id": trade.id,
                    "tradingAccountId": trade.trading_account_id,
                    "source": trade.source.value,
                    "externalPositionId": trade.external_position_id,
                    "symbol": trade.symbol,
                    "assetClass": trade.asset_class.value,
                    "direction": trade.direction.value,
                    "status": trade.status.value,
                    "openedAt": trade.opened_at.astimezone(UTC).isoformat(),
                    "closedAt": (
                        trade.closed_at.astimezone(UTC).isoformat()
                        if trade.closed_at
                        else None
                    ),
                    "averageEntryPrice": format_decimal(trade.average_entry_price),
                    "averageExitPrice": format_decimal(trade.average_exit_price),
                    "initialVolume": str(trade.initial_volume),
                    "netPnl": str(trade.net_pnl),
                    "commission": str(trade.commission),
                    "swap": str(trade.swap),
                    "realizedR": (
                        str(trade.realized_r) if trade.realized_r is not None else None
                    ),
                    "strategyIds": [
                        entry.strategy.id for entry in trade.trade_strategies
                    ],
                }
                for trade in trades
            ],
        }

    async def _build_import_preview(
        self, user_id: str, input_data: CsvImportPreviewInput
    ) -> dict[str, object]:
        await self._accounts_service.find_by_id_for_user(
            input_data.trading_account_id, user_id
        )

        parsed = parse_csv(input_data.csv)
        mapped = map_csv_trades(parsed, input_data.format)
        existing_keys = await self._load_existing_duplicate_keys(
            user_id, input_data.trading_account_id
        )

        valid_rows = []
        for trade in mapped["trades"]:
            duplicate_key = build_duplicate_key(trade)
            valid_rows.append(
                {
                    "rowNumber": trade.row_number,
                    "trade": trade,
                    "duplicateKey": duplicate_key,
                    "isDuplicate": duplicate_key in existing_keys,
                }
            )

        return {
            "format": mapped["format"],
            "totalRows": len(parsed.rows),
            "validCount": len(valid_rows),
            "duplicateCount": sum(1 for row in valid_rows if row["isDuplicate"]),
            "invalidCount": len(mapped["errors"]),
            "validRows": valid_rows,
            "rowErrors": [
                {"rowNumber": error.row_number, "message": error.message}
                for error in mapped["errors"]
            ],
            "preview": [
                {
                    "rowNumber": row["rowNumber"],
                    "symbol": row["trade"].symbol,
                    "direction": row["trade"].direction,
                    "openedAt": row["trade"].opened_at.astimezone(UTC).isoformat(),
                    "closedAt": row["trade"].closed_at.astimezone(UTC).isoformat(),
                    "netPnl": row["trade"].net_pnl,
                    "isDuplicate": row["isDuplicate"],
                }
                for row in valid_rows[:10]
            ],
        }

    async def _resolve_instrument(
        self, account_id: str, symbol: str, user_id: str
    ):
        instruments = await self._instruments_service.list_for_account(account_id, user_id)
        instrument = next(
            (
                row
                for row in instruments
                if row.symbol.upper() == symbol.upper()
            ),
            None,
        )

        if instrument is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Instrument {symbol} is not configured for this account.",
            )

        return instrument

    async def _load_existing_duplicate_keys(
        self, user_id: str, trading_account_id: str
    ) -> set[str]:
        result = await self._db.execute(
            select(Trade).where(
                Trade.user_id == user_id,
                Trade.trading_account_id == trading_account_id,
            )
        )
        trades = result.scalars().all()
        keys: set[str] = set()

        for trade in trades:
            keys.add(
                build_duplicate_key(
                    MappedCsvTrade(
                        row_number=0,
                        external_position_id=trade.external_position_id,
                        symbol=trade.symbol,
                        direction="LONG",
                        opened_at=trade.opened_at,
                        closed_at=trade.closed_at or trade.opened_at,
                        entry_price=float(trade.average_entry_price),
                        exit_price=float(trade.average_entry_price),
                        volume=float(trade.initial_volume),
                        stop_loss=None,
                        take_profit=None,
                        commission=0,
                        swap=0,
                        net_pnl=0,
                    )
                )
            )

        return keys

    async def _load_export_trades(
        self, user_id: str, query: ExportQuery
    ) -> list[Trade]:
        if query.trading_account_id:
            await self._accounts_service.find_by_id_for_user(
                query.trading_account_id, user_id
            )

        trade_query = select(Trade).where(Trade.user_id == user_id)
        if query.trading_account_id:
            trade_query = trade_query.where(
                Trade.trading_account_id == query.trading_account_id
            )

        result = await self._db.execute(
            trade_query.options(
                selectinload(Trade.trade_strategies).selectinload(TradeStrategy.strategy)
            ).order_by(Trade.opened_at.desc())
        )
        return list(result.scalars().all())


async def get_import_export_service(
    db: DbSession,
    accounts_service: AccountsServiceDep,
    instruments_service: InstrumentsServiceDep,
) -> ImportExportService:
    return ImportExportService(db, accounts_service, instruments_service)


ImportExportServiceDep = Annotated[
    ImportExportService, Depends(get_import_export_service)
]
