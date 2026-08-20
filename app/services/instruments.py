from decimal import Decimal
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.default_instruments import DEFAULT_INSTRUMENT_SPECS
from app.dependencies.database import DbSession
from app.models.models import InstrumentSpec
from app.schemas.instrument import CreateInstrumentInput, UpdateInstrumentInput
from app.services.accounts import AccountsService, AccountsServiceDep
from app.utils.ids import generate_cuid


class InstrumentsService:
    def __init__(self, db: AsyncSession, accounts_service: AccountsService) -> None:
        self._db = db
        self._accounts_service = accounts_service

    async def list_for_account(self, account_id: str, user_id: str) -> list[InstrumentSpec]:
        await self._accounts_service.find_by_id_for_user(account_id, user_id)

        result = await self._db.execute(
            select(InstrumentSpec)
            .where(InstrumentSpec.trading_account_id == account_id)
            .order_by(InstrumentSpec.symbol.asc())
        )
        instruments = list(result.scalars().all())

        if not instruments:
            await self.seed_defaults_for_account(account_id)
            result = await self._db.execute(
                select(InstrumentSpec)
                .where(InstrumentSpec.trading_account_id == account_id)
                .order_by(InstrumentSpec.symbol.asc())
            )
            instruments = list(result.scalars().all())

        return instruments

    async def find_by_id_for_account(
        self,
        instrument_id: str,
        account_id: str,
        user_id: str,
    ) -> InstrumentSpec:
        await self._accounts_service.find_by_id_for_user(account_id, user_id)

        result = await self._db.execute(
            select(InstrumentSpec).where(
                InstrumentSpec.id == instrument_id,
                InstrumentSpec.trading_account_id == account_id,
            )
        )
        instrument = result.scalar_one_or_none()

        if instrument is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Instrument specification not found",
            )

        return instrument

    async def create_for_account(
        self,
        account_id: str,
        user_id: str,
        input_data: CreateInstrumentInput,
    ) -> InstrumentSpec:
        await self._accounts_service.find_by_id_for_user(account_id, user_id)

        instrument = InstrumentSpec(
            id=generate_cuid(),
            **self._to_create_data(account_id, input_data),
        )
        self._db.add(instrument)
        await self._db.commit()
        await self._db.refresh(instrument)
        return instrument

    async def update_for_account(
        self,
        instrument_id: str,
        account_id: str,
        user_id: str,
        input_data: UpdateInstrumentInput,
    ) -> InstrumentSpec:
        instrument = await self.find_by_id_for_account(
            instrument_id, account_id, user_id
        )

        for key, value in self._to_update_data(input_data).items():
            setattr(instrument, key, value)

        await self._db.commit()
        await self._db.refresh(instrument)
        return instrument

    async def seed_defaults_for_account(self, account_id: str) -> None:
        for spec in DEFAULT_INSTRUMENT_SPECS:
            existing = await self._db.execute(
                select(InstrumentSpec).where(
                    InstrumentSpec.trading_account_id == account_id,
                    InstrumentSpec.symbol == spec["symbol"],
                )
            )
            if existing.scalar_one_or_none():
                continue

            self._db.add(
                InstrumentSpec(
                    id=generate_cuid(),
                    trading_account_id=account_id,
                    symbol=spec["symbol"],
                    description=spec.get("description"),
                    asset_class=spec["asset_class"],
                    digits=spec["digits"],
                    point=Decimal(str(spec["point"])),
                    tick_size=Decimal(str(spec["tick_size"])),
                    tick_value_profit=Decimal(str(spec["tick_value_profit"])),
                    tick_value_loss=Decimal(str(spec["tick_value_loss"])),
                    contract_size=Decimal(str(spec["contract_size"])),
                    volume_min=Decimal(str(spec["volume_min"])),
                    volume_max=Decimal(str(spec["volume_max"])),
                    volume_step=Decimal(str(spec["volume_step"])),
                    base_currency=spec.get("base_currency"),
                    profit_currency=spec.get("profit_currency"),
                )
            )

        await self._db.commit()

    @staticmethod
    def to_instrument_response(instrument: InstrumentSpec) -> dict[str, object]:
        return {
            "id": instrument.id,
            "tradingAccountId": instrument.trading_account_id,
            "symbol": instrument.symbol,
            "description": instrument.description,
            "assetClass": instrument.asset_class.value,
            "digits": instrument.digits,
            "point": str(instrument.point),
            "tickSize": str(instrument.tick_size),
            "tickValueProfit": str(instrument.tick_value_profit),
            "tickValueLoss": str(instrument.tick_value_loss),
            "contractSize": str(instrument.contract_size),
            "volumeMin": str(instrument.volume_min),
            "volumeMax": str(instrument.volume_max),
            "volumeStep": str(instrument.volume_step),
            "baseCurrency": instrument.base_currency,
            "profitCurrency": instrument.profit_currency,
            "createdAt": instrument.created_at.isoformat(),
            "updatedAt": instrument.updated_at.isoformat(),
        }

    @staticmethod
    def _to_create_data(account_id: str, input_data: CreateInstrumentInput) -> dict:
        return {
            "trading_account_id": account_id,
            "symbol": input_data.symbol.upper(),
            "description": input_data.description,
            "asset_class": input_data.asset_class,
            "digits": input_data.digits,
            "point": Decimal(str(input_data.point)),
            "tick_size": Decimal(str(input_data.tick_size)),
            "tick_value_profit": Decimal(str(input_data.tick_value_profit)),
            "tick_value_loss": Decimal(str(input_data.tick_value_loss)),
            "contract_size": Decimal(str(input_data.contract_size)),
            "volume_min": Decimal(str(input_data.volume_min)),
            "volume_max": Decimal(str(input_data.volume_max)),
            "volume_step": Decimal(str(input_data.volume_step)),
            "base_currency": (
                input_data.base_currency.upper() if input_data.base_currency else None
            ),
            "profit_currency": (
                input_data.profit_currency.upper() if input_data.profit_currency else None
            ),
        }

    @staticmethod
    def _to_update_data(input_data: UpdateInstrumentInput) -> dict:
        data: dict = {}

        if "symbol" in input_data.model_fields_set and input_data.symbol is not None:
            data["symbol"] = input_data.symbol.upper()
        if "description" in input_data.model_fields_set:
            data["description"] = input_data.description
        if "asset_class" in input_data.model_fields_set and input_data.asset_class is not None:
            data["asset_class"] = input_data.asset_class
        if "digits" in input_data.model_fields_set and input_data.digits is not None:
            data["digits"] = input_data.digits
        if "point" in input_data.model_fields_set and input_data.point is not None:
            data["point"] = Decimal(str(input_data.point))
        if "tick_size" in input_data.model_fields_set and input_data.tick_size is not None:
            data["tick_size"] = Decimal(str(input_data.tick_size))
        if (
            "tick_value_profit" in input_data.model_fields_set
            and input_data.tick_value_profit is not None
        ):
            data["tick_value_profit"] = Decimal(str(input_data.tick_value_profit))
        if (
            "tick_value_loss" in input_data.model_fields_set
            and input_data.tick_value_loss is not None
        ):
            data["tick_value_loss"] = Decimal(str(input_data.tick_value_loss))
        if (
            "contract_size" in input_data.model_fields_set
            and input_data.contract_size is not None
        ):
            data["contract_size"] = Decimal(str(input_data.contract_size))
        if "volume_min" in input_data.model_fields_set and input_data.volume_min is not None:
            data["volume_min"] = Decimal(str(input_data.volume_min))
        if "volume_max" in input_data.model_fields_set and input_data.volume_max is not None:
            data["volume_max"] = Decimal(str(input_data.volume_max))
        if "volume_step" in input_data.model_fields_set and input_data.volume_step is not None:
            data["volume_step"] = Decimal(str(input_data.volume_step))
        if "base_currency" in input_data.model_fields_set and input_data.base_currency is not None:
            data["base_currency"] = input_data.base_currency.upper()
        if (
            "profit_currency" in input_data.model_fields_set
            and input_data.profit_currency is not None
        ):
            data["profit_currency"] = input_data.profit_currency.upper()

        return data


async def get_instruments_service(
    db: DbSession,
    accounts_service: AccountsServiceDep,
) -> InstrumentsService:
    return InstrumentsService(db, accounts_service)


InstrumentsServiceDep = Annotated[InstrumentsService, Depends(get_instruments_service)]
