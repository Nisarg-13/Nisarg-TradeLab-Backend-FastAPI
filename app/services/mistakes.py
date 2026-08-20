from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Mistake
from app.schemas.strategy import (
    CreateMistakeInput,
    MistakeResponse,
    UpdateMistakeInput,
)
from app.utils.ids import generate_cuid
from app.utils.ownership import assert_resource_ownership


class MistakesService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_for_user(self, user_id: str) -> list[Mistake]:
        result = await self._db.execute(
            select(Mistake).where(Mistake.user_id == user_id).order_by(Mistake.name.asc())
        )
        return list(result.scalars().all())

    async def create_for_user(
        self,
        user_id: str,
        input_data: CreateMistakeInput,
    ) -> Mistake:
        mistake = Mistake(
            id=generate_cuid(),
            user_id=user_id,
            name=input_data.name,
        )
        self._db.add(mistake)
        await self._db.commit()
        await self._db.refresh(mistake)
        return mistake

    async def update_for_user(
        self,
        mistake_id: str,
        user_id: str,
        input_data: UpdateMistakeInput,
    ) -> Mistake:
        mistake = await self.find_by_id_for_user(mistake_id, user_id)
        mistake.name = input_data.name
        await self._db.commit()
        await self._db.refresh(mistake)
        return mistake

    async def delete_for_user(self, mistake_id: str, user_id: str) -> None:
        mistake = await self.find_by_id_for_user(mistake_id, user_id)
        await self._db.delete(mistake)
        await self._db.commit()

    async def find_by_id_for_user(self, mistake_id: str, user_id: str) -> Mistake:
        result = await self._db.execute(select(Mistake).where(Mistake.id == mistake_id))
        mistake = result.scalar_one_or_none()

        if not mistake:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mistake not found",
            )

        assert_resource_ownership(mistake.user_id, user_id)
        return mistake

    @staticmethod
    def to_mistake_response(mistake: Mistake) -> MistakeResponse:
        return MistakeResponse(
            id=mistake.id,
            name=mistake.name,
            createdAt=mistake.created_at.isoformat(),
            updatedAt=mistake.updated_at.isoformat(),
        )
