from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.dependencies.database import DbSession
from app.models.models import MT5Connection, User
from app.utils.mt5_key import verify_connection_key


async def get_mt5_secret(settings: Annotated[Settings, Depends(get_settings)]) -> str:
    return settings.MT5_CONNECTION_TOKEN_SECRET or "development-mt5-secret"


async def get_mt5_connection(
    request: Request,
    db: DbSession,
    secret: Annotated[str, Depends(get_mt5_secret)],
) -> MT5Connection:
    authorization = request.headers.get("authorization")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing MT5 connection key",
        )

    key = authorization[len("Bearer ") :].strip()

    if not key.startswith("TJ_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MT5 connection key",
        )

    result = await db.execute(select(MT5Connection))
    connections = result.scalars().all()

    connection = next(
        (
            item
            for item in connections
            if verify_connection_key(key, item.connection_key_hash, secret)
        ),
        None,
    )

    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MT5 connection key",
        )

    request.state.mt5_connection = connection
    return connection


Mt5ConnectionDep = Annotated[MT5Connection, Depends(get_mt5_connection)]
