from decimal import Decimal
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.data.default_instruments import DEFAULT_INSTRUMENT_SPECS
from app.dependencies.database import DbSession
from app.models.models import RiskSettings, TradingAccount
from app.schemas.account import (
    CreateAccountInput,
    UpdateAccountInput,
    UpdateRiskSettingsInput,
)
from app.services.users import UsersService, get_users_service
from app.utils.ids import generate_cuid
from app.utils.ownership import assert_resource_ownership


class AccountsService:
    def __init__(self, db: AsyncSession, users_service: UsersService) -> None:
        self._db = db
        self._users_service = users_service

    async def list_for_user(
        self, user_id: str, include_archived: bool = False
    ) -> list[TradingAccount]:
        query = select(TradingAccount).where(TradingAccount.user_id == user_id)

        if not include_archived:
            query = query.where(TradingAccount.is_active.is_(True))

        query = query.options(selectinload(TradingAccount.risk_settings)).order_by(
            TradingAccount.created_at.desc()
        )

        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def find_by_id_for_user(self, account_id: str, user_id: str) -> TradingAccount:
        result = await self._db.execute(
            select(TradingAccount)
            .where(TradingAccount.id == account_id)
            .options(selectinload(TradingAccount.risk_settings))
        )
        account = result.scalar_one_or_none()

        if account is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trading account not found",
            )

        assert_resource_ownership(account.user_id, user_id)
        return account

    async def create_for_user(
        self, user_id: str, input_data: CreateAccountInput
    ) -> TradingAccount:
        current_balance = (
            input_data.current_balance
            if input_data.current_balance is not None
            else input_data.starting_balance
        )

        account = TradingAccount(
            id=generate_cuid(),
            user_id=user_id,
            name=input_data.name,
            type=input_data.type,
            broker_name=input_data.broker_name,
            currency=input_data.currency.upper(),
            starting_balance=Decimal(str(input_data.starting_balance)),
            current_balance=Decimal(str(current_balance)),
        )
        self._db.add(account)
        await self._db.flush()

        risk_settings = RiskSettings(
            id=generate_cuid(),
            trading_account_id=account.id,
        )
        self._db.add(risk_settings)

        for spec in DEFAULT_INSTRUMENT_SPECS:
            self._db.add(
                _instrument_from_spec(account.id, spec),
            )

        await self._db.commit()
        await self._db.refresh(account, ["risk_settings"])
        return account

    async def update_for_user(
        self,
        account_id: str,
        user_id: str,
        input_data: UpdateAccountInput,
    ) -> TradingAccount:
        await self.find_by_id_for_user(account_id, user_id)

        result = await self._db.execute(
            select(TradingAccount)
            .where(TradingAccount.id == account_id)
            .options(selectinload(TradingAccount.risk_settings))
        )
        account = result.scalar_one()

        if "name" in input_data.model_fields_set and input_data.name is not None:
            account.name = input_data.name
        if "type" in input_data.model_fields_set and input_data.type is not None:
            account.type = input_data.type
        if "broker_name" in input_data.model_fields_set:
            account.broker_name = input_data.broker_name
        if "currency" in input_data.model_fields_set and input_data.currency is not None:
            account.currency = input_data.currency.upper()
        if (
            "current_balance" in input_data.model_fields_set
            and input_data.current_balance is not None
        ):
            account.current_balance = Decimal(str(input_data.current_balance))

        await self._db.commit()
        await self._db.refresh(account, ["risk_settings"])
        return account

    async def archive_for_user(self, account_id: str, user_id: str) -> TradingAccount:
        await self.find_by_id_for_user(account_id, user_id)

        await self._users_service.clear_selected_trading_account_for_users(account_id)

        result = await self._db.execute(
            select(TradingAccount)
            .where(TradingAccount.id == account_id)
            .options(selectinload(TradingAccount.risk_settings))
        )
        account = result.scalar_one()
        account.is_active = False

        await self._db.commit()
        await self._db.refresh(account, ["risk_settings"])
        return account

    async def get_risk_settings(self, account_id: str, user_id: str) -> RiskSettings:
        account = await self.find_by_id_for_user(account_id, user_id)

        if account.risk_settings is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Risk settings not found",
            )

        return account.risk_settings

    async def update_risk_settings(
        self,
        account_id: str,
        user_id: str,
        input_data: UpdateRiskSettingsInput,
    ) -> RiskSettings:
        await self.find_by_id_for_user(account_id, user_id)

        result = await self._db.execute(
            select(RiskSettings).where(RiskSettings.trading_account_id == account_id)
        )
        settings = result.scalar_one_or_none()

        if settings is None:
            settings = RiskSettings(
                id=generate_cuid(),
                trading_account_id=account_id,
                default_risk_percentage=Decimal(
                    str(input_data.default_risk_percentage or 1)
                ),
                max_risk_per_trade_percentage=Decimal(
                    str(input_data.max_risk_per_trade_percentage or 2)
                ),
                max_daily_risk_percentage=Decimal(
                    str(input_data.max_daily_risk_percentage or 5)
                ),
                max_daily_loss_percentage=Decimal(
                    str(input_data.max_daily_loss_percentage or 5)
                ),
                max_open_risk_percentage=Decimal(
                    str(input_data.max_open_risk_percentage or 10)
                ),
                max_trades_per_day=input_data.max_trades_per_day or 5,
                max_consecutive_losses=input_data.max_consecutive_losses or 3,
                strict_mode=input_data.strict_mode or False,
            )
            self._db.add(settings)
        else:
            if (
                "default_risk_percentage" in input_data.model_fields_set
                and input_data.default_risk_percentage is not None
            ):
                settings.default_risk_percentage = Decimal(
                    str(input_data.default_risk_percentage)
                )
            if (
                "max_risk_per_trade_percentage" in input_data.model_fields_set
                and input_data.max_risk_per_trade_percentage is not None
            ):
                settings.max_risk_per_trade_percentage = Decimal(
                    str(input_data.max_risk_per_trade_percentage)
                )
            if (
                "max_daily_risk_percentage" in input_data.model_fields_set
                and input_data.max_daily_risk_percentage is not None
            ):
                settings.max_daily_risk_percentage = Decimal(
                    str(input_data.max_daily_risk_percentage)
                )
            if (
                "max_daily_loss_percentage" in input_data.model_fields_set
                and input_data.max_daily_loss_percentage is not None
            ):
                settings.max_daily_loss_percentage = Decimal(
                    str(input_data.max_daily_loss_percentage)
                )
            if (
                "max_open_risk_percentage" in input_data.model_fields_set
                and input_data.max_open_risk_percentage is not None
            ):
                settings.max_open_risk_percentage = Decimal(
                    str(input_data.max_open_risk_percentage)
                )
            if (
                "max_trades_per_day" in input_data.model_fields_set
                and input_data.max_trades_per_day is not None
            ):
                settings.max_trades_per_day = input_data.max_trades_per_day
            if (
                "max_consecutive_losses" in input_data.model_fields_set
                and input_data.max_consecutive_losses is not None
            ):
                settings.max_consecutive_losses = input_data.max_consecutive_losses
            if "strict_mode" in input_data.model_fields_set and input_data.strict_mode is not None:
                settings.strict_mode = input_data.strict_mode

        await self._db.commit()
        await self._db.refresh(settings)
        return settings

    @staticmethod
    def to_account_response(account: TradingAccount) -> dict[str, object]:
        return {
            "id": account.id,
            "name": account.name,
            "type": account.type.value,
            "source": account.source.value,
            "brokerName": account.broker_name,
            "currency": account.currency,
            "startingBalance": str(account.starting_balance),
            "currentBalance": str(account.current_balance),
            "isActive": account.is_active,
            "createdAt": account.created_at.isoformat(),
            "updatedAt": account.updated_at.isoformat(),
            "riskSettings": (
                AccountsService.to_risk_settings_response(account.risk_settings)
                if account.risk_settings
                else None
            ),
        }

    @staticmethod
    def to_risk_settings_response(settings: RiskSettings) -> dict[str, object]:
        return {
            "id": settings.id,
            "tradingAccountId": settings.trading_account_id,
            "defaultRiskPercentage": str(settings.default_risk_percentage),
            "maxRiskPerTradePercentage": str(settings.max_risk_per_trade_percentage),
            "maxDailyRiskPercentage": str(settings.max_daily_risk_percentage),
            "maxDailyLossPercentage": str(settings.max_daily_loss_percentage),
            "maxOpenRiskPercentage": str(settings.max_open_risk_percentage),
            "maxTradesPerDay": settings.max_trades_per_day,
            "maxConsecutiveLosses": settings.max_consecutive_losses,
            "strictMode": settings.strict_mode,
            "createdAt": settings.created_at.isoformat(),
            "updatedAt": settings.updated_at.isoformat(),
        }


def _instrument_from_spec(account_id: str, spec: dict) -> object:
    from app.models.models import InstrumentSpec

    return InstrumentSpec(
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


async def get_accounts_service(
    db: DbSession,
    users_service: Annotated[UsersService, Depends(get_users_service)],
) -> AccountsService:
    return AccountsService(db, users_service)


AccountsServiceDep = Annotated[AccountsService, Depends(get_accounts_service)]
