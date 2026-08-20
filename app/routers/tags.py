from fastapi import APIRouter, Request

from app.dependencies.services import CurrentUser, TagsServiceDep
from app.schemas.common import DataEnvelope
from app.schemas.strategy import (
    CreateTagInput,
    SuccessResponse,
    TagResponse,
    UpdateTagInput,
)
from app.utils.validation import parse_body

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("")
async def list_tags(
    current_user: CurrentUser,
    tags_service: TagsServiceDep,
) -> DataEnvelope[list[TagResponse]]:
    tags = await tags_service.list_for_user(current_user.id)
    return DataEnvelope(data=[tags_service.to_tag_response(tag) for tag in tags])


@router.post("")
async def create_tag(
    request: Request,
    current_user: CurrentUser,
    tags_service: TagsServiceDep,
) -> DataEnvelope[TagResponse]:
    body = await request.json()
    parsed = parse_body(CreateTagInput, body)
    tag = await tags_service.create_for_user(current_user.id, parsed)  # type: ignore[arg-type]
    return DataEnvelope(data=tags_service.to_tag_response(tag))


@router.patch("/{tag_id}")
async def update_tag(
    tag_id: str,
    request: Request,
    current_user: CurrentUser,
    tags_service: TagsServiceDep,
) -> DataEnvelope[TagResponse]:
    body = await request.json()
    parsed = parse_body(UpdateTagInput, body)
    tag = await tags_service.update_for_user(tag_id, current_user.id, parsed)  # type: ignore[arg-type]
    return DataEnvelope(data=tags_service.to_tag_response(tag))


@router.delete("/{tag_id}")
async def delete_tag(
    tag_id: str,
    current_user: CurrentUser,
    tags_service: TagsServiceDep,
) -> DataEnvelope[SuccessResponse]:
    await tags_service.delete_for_user(tag_id, current_user.id)
    return DataEnvelope(data=SuccessResponse(success=True))
