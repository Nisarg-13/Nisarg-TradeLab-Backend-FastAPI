from fastapi import APIRouter, Request

from app.dependencies.services import CurrentUser, MistakesServiceDep
from app.schemas.common import DataEnvelope
from app.schemas.strategy import (
    CreateMistakeInput,
    MistakeResponse,
    SuccessResponse,
    UpdateMistakeInput,
)
from app.utils.validation import parse_body

router = APIRouter(prefix="/mistakes", tags=["mistakes"])


@router.get("")
async def list_mistakes(
    current_user: CurrentUser,
    mistakes_service: MistakesServiceDep,
) -> DataEnvelope[list[MistakeResponse]]:
    mistakes = await mistakes_service.list_for_user(current_user.id)
    return DataEnvelope(
        data=[mistakes_service.to_mistake_response(mistake) for mistake in mistakes]
    )


@router.post("")
async def create_mistake(
    request: Request,
    current_user: CurrentUser,
    mistakes_service: MistakesServiceDep,
) -> DataEnvelope[MistakeResponse]:
    body = await request.json()
    parsed = parse_body(CreateMistakeInput, body)
    mistake = await mistakes_service.create_for_user(
        current_user.id,
        parsed,  # type: ignore[arg-type]
    )
    return DataEnvelope(data=mistakes_service.to_mistake_response(mistake))


@router.patch("/{mistake_id}")
async def update_mistake(
    mistake_id: str,
    request: Request,
    current_user: CurrentUser,
    mistakes_service: MistakesServiceDep,
) -> DataEnvelope[MistakeResponse]:
    body = await request.json()
    parsed = parse_body(UpdateMistakeInput, body)
    mistake = await mistakes_service.update_for_user(
        mistake_id,
        current_user.id,
        parsed,  # type: ignore[arg-type]
    )
    return DataEnvelope(data=mistakes_service.to_mistake_response(mistake))


@router.delete("/{mistake_id}")
async def delete_mistake(
    mistake_id: str,
    current_user: CurrentUser,
    mistakes_service: MistakesServiceDep,
) -> DataEnvelope[SuccessResponse]:
    await mistakes_service.delete_for_user(mistake_id, current_user.id)
    return DataEnvelope(data=SuccessResponse(success=True))
