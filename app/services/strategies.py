from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Strategy
from app.schemas.strategy import (
    CreateStrategyInput,
    StrategyResponse,
    UpdateStrategyInput,
)
from app.utils.ids import generate_cuid
from app.utils.ownership import assert_resource_ownership


class StrategiesService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_for_user(self, user_id: str) -> list[Strategy]:
        result = await self._db.execute(
            select(Strategy)
            .where(Strategy.user_id == user_id)
            .order_by(Strategy.name.asc())
        )
        return list(result.scalars().all())

    async def create_for_user(
        self,
        user_id: str,
        input_data: CreateStrategyInput,
    ) -> Strategy:
        strategy = Strategy(
            id=generate_cuid(),
            user_id=user_id,
            name=input_data.name,
            description=input_data.description,
        )
        self._db.add(strategy)
        await self._db.commit()
        await self._db.refresh(strategy)
        return strategy

    async def update_for_user(
        self,
        strategy_id: str,
        user_id: str,
        input_data: UpdateStrategyInput,
    ) -> Strategy:
        strategy = await self.find_by_id_for_user(strategy_id, user_id)

        if input_data.name is not None:
            strategy.name = input_data.name
        if input_data.description is not None:
            strategy.description = input_data.description
        if input_data.is_active is not None:
            strategy.is_active = input_data.is_active

        await self._db.commit()
        await self._db.refresh(strategy)
        return strategy

    async def delete_for_user(self, strategy_id: str, user_id: str) -> None:
        strategy = await self.find_by_id_for_user(strategy_id, user_id)
        await self._db.delete(strategy)
        await self._db.commit()

    async def find_by_id_for_user(self, strategy_id: str, user_id: str) -> Strategy:
        result = await self._db.execute(select(Strategy).where(Strategy.id == strategy_id))
        strategy = result.scalar_one_or_none()

        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Strategy not found",
            )

        assert_resource_ownership(strategy.user_id, user_id)
        return strategy

    @staticmethod
    def to_strategy_response(strategy: Strategy) -> StrategyResponse:
        return StrategyResponse(
            id=strategy.id,
            name=strategy.name,
            description=strategy.description,
            isActive=strategy.is_active,
            createdAt=strategy.created_at.isoformat(),
            updatedAt=strategy.updated_at.isoformat(),
        )
