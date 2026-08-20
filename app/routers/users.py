from fastapi import APIRouter, Request

from app.dependencies.services import CurrentUser, UsersServiceDep
from app.schemas.common import DataEnvelope
from app.schemas.user import UpdateUserInput, UserResponse
from app.utils.validation import parse_body

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_current_user_profile(
    user: CurrentUser,
    users_service: UsersServiceDep,
) -> DataEnvelope[UserResponse]:
    return DataEnvelope(data=users_service.to_response(user))


@router.patch("/me")
async def update_current_user_profile(
    request: Request,
    user: CurrentUser,
    users_service: UsersServiceDep,
) -> DataEnvelope[UserResponse]:
    body = await request.json()
    parsed = parse_body(UpdateUserInput, body)
    updated = await users_service.update_profile(user.id, parsed)  # type: ignore[arg-type]
    return DataEnvelope(data=users_service.to_response(updated))
