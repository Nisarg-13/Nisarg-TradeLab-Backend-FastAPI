from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db
from app.models.models import User
from app.services.clerk import ClerkService, get_clerk_service
from app.services.users import UsersService, get_users_service


@dataclass(frozen=True, slots=True)
class AuthenticatedClerkUser:
    clerk_user_id: str


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_clerk_user(
    request: Request,
    clerk_service: Annotated[ClerkService, Depends(get_clerk_service)],
) -> AuthenticatedClerkUser:
    authorization = request.headers.get("authorization")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    token = authorization[len("Bearer ") :].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    clerk_user_id = await clerk_service.verify_bearer_token(token)
    clerk_user = AuthenticatedClerkUser(clerk_user_id=clerk_user_id)
    request.state.clerk_user = clerk_user
    return clerk_user


async def get_current_user(
    clerk_user: Annotated[AuthenticatedClerkUser, Depends(get_current_clerk_user)],
    users_service: Annotated[UsersService, Depends(get_users_service)],
) -> User:
    return await users_service.find_or_create_by_clerk_user_id(clerk_user.clerk_user_id)


CurrentClerkUser = Annotated[AuthenticatedClerkUser, Depends(get_current_clerk_user)]
CurrentUser = Annotated[User, Depends(get_current_user)]
