from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import DbSession
from app.models.models import TradingAccount, User
from app.schemas.user import UpdateUserInput, UserFeaturesResponse, UserResponse
from app.services.clerk import ClerkService, get_clerk_service
from app.utils.ai_coach_access import is_ai_coach_enabled
from app.utils.ids import generate_cuid


class UsersService:
    def __init__(self, db: AsyncSession, clerk_service: ClerkService) -> None:
        self._db = db
        self._clerk_service = clerk_service

    async def find_or_create_by_clerk_user_id(self, clerk_user_id: str) -> User:
        result = await self._db.execute(
            select(User).where(User.clerk_user_id == clerk_user_id)
        )
        existing = result.scalar_one_or_none()

        email = await self._clerk_service.get_primary_email(clerk_user_id)

        if existing:
            if existing.email != email:
                existing.email = email
                await self._db.commit()
                await self._db.refresh(existing)
            return existing

        user = User(
            id=generate_cuid(),
            clerk_user_id=clerk_user_id,
            email=email,
        )
        self._db.add(user)
        await self._db.commit()
        await self._db.refresh(user)
        return user

    async def update_profile(self, user_id: str, input_data: UpdateUserInput) -> User:
        data: dict[str, object] = {}

        if "timezone" in input_data.model_fields_set:
            data["timezone"] = input_data.timezone

        if "preferred_currency" in input_data.model_fields_set:
            data["preferred_currency"] = input_data.preferred_currency

        if "selected_trading_account_id" in input_data.model_fields_set:
            data["selected_trading_account_id"] = await self.resolve_selected_trading_account_id(
                user_id,
                input_data.selected_trading_account_id,
            )

        result = await self._db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()

        for key, value in data.items():
            setattr(user, key, value)

        await self._db.commit()
        await self._db.refresh(user)
        return user

    async def resolve_selected_trading_account_id(
        self,
        user_id: str,
        account_id: str | None,
    ) -> str | None:
        if not account_id:
            return None

        result = await self._db.execute(
            select(TradingAccount.id).where(
                TradingAccount.id == account_id,
                TradingAccount.user_id == user_id,
                TradingAccount.is_active.is_(True),
            )
        )
        account = result.scalar_one_or_none()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trading account not found.",
            )

        return account

    async def clear_selected_trading_account_for_users(self, account_id: str) -> None:
        await self._db.execute(
            update(User)
            .where(User.selected_trading_account_id == account_id)
            .values(selected_trading_account_id=None)
        )

    @staticmethod
    def to_response(user: User) -> UserResponse:
        return UserResponse(
            id=user.id,
            email=user.email,
            timezone=user.timezone,
            preferredCurrency=user.preferred_currency,
            selectedTradingAccountId=user.selected_trading_account_id,
            createdAt=user.created_at.isoformat(),
            updatedAt=user.updated_at.isoformat(),
            features=UserFeaturesResponse(aiCoach=is_ai_coach_enabled(user.email)),
        )


def get_users_service(
    db: DbSession,
    clerk_service: Annotated[ClerkService, Depends(get_clerk_service)],
) -> UsersService:
    return UsersService(db, clerk_service)


UsersServiceDep = Annotated[UsersService, Depends(get_users_service)]
