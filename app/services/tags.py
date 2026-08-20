from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Tag
from app.schemas.strategy import CreateTagInput, TagResponse, UpdateTagInput
from app.utils.ids import generate_cuid
from app.utils.ownership import assert_resource_ownership


class TagsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_for_user(self, user_id: str) -> list[Tag]:
        result = await self._db.execute(
            select(Tag).where(Tag.user_id == user_id).order_by(Tag.name.asc())
        )
        return list(result.scalars().all())

    async def create_for_user(self, user_id: str, input_data: CreateTagInput) -> Tag:
        tag = Tag(
            id=generate_cuid(),
            user_id=user_id,
            name=input_data.name,
        )
        self._db.add(tag)
        await self._db.commit()
        await self._db.refresh(tag)
        return tag

    async def update_for_user(
        self,
        tag_id: str,
        user_id: str,
        input_data: UpdateTagInput,
    ) -> Tag:
        tag = await self.find_by_id_for_user(tag_id, user_id)
        tag.name = input_data.name
        await self._db.commit()
        await self._db.refresh(tag)
        return tag

    async def delete_for_user(self, tag_id: str, user_id: str) -> None:
        tag = await self.find_by_id_for_user(tag_id, user_id)
        await self._db.delete(tag)
        await self._db.commit()

    async def find_by_id_for_user(self, tag_id: str, user_id: str) -> Tag:
        result = await self._db.execute(select(Tag).where(Tag.id == tag_id))
        tag = result.scalar_one_or_none()

        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tag not found",
            )

        assert_resource_ownership(tag.user_id, user_id)
        return tag

    @staticmethod
    def to_tag_response(tag: Tag) -> TagResponse:
        return TagResponse(
            id=tag.id,
            name=tag.name,
            createdAt=tag.created_at.isoformat(),
            updatedAt=tag.updated_at.isoformat(),
        )
