from functools import lru_cache

from clerk_backend_api import Clerk
from clerk_backend_api.security import verify_token
from clerk_backend_api.security.types import VerifyTokenOptions
from fastapi import HTTPException, status

from app.config import Settings, get_settings


class ClerkService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _get_secret_key(self) -> str:
        secret_key = self._settings.CLERK_SECRET_KEY
        if not secret_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication is not configured",
            )
        return secret_key

    @property
    def client(self) -> Clerk:
        return Clerk(bearer_auth=self._get_secret_key())

    async def verify_bearer_token(self, token: str) -> str:
        try:
            payload = verify_token(
                token,
                VerifyTokenOptions(secret_key=self._get_secret_key()),
            )
            clerk_user_id = payload.get("sub")
            if not clerk_user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication token",
                )
            return str(clerk_user_id)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            ) from exc

    async def get_primary_email(self, clerk_user_id: str) -> str:
        try:
            user = self.client.users.get(user_id=clerk_user_id)
            primary_email = next(
                (
                    address.email_address
                    for address in user.email_addresses or []
                    if address.id == user.primary_email_address_id
                ),
                None,
            )
            if not primary_email:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Clerk user has no primary email",
                )
            return primary_email
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Clerk user has no primary email",
            ) from exc


@lru_cache
def get_clerk_service() -> ClerkService:
    return ClerkService(get_settings())
