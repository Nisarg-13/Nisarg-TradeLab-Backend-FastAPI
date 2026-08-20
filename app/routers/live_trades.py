from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.dependencies.auth import CurrentClerkUser
from app.services.live_trades import LiveTradesServiceDep
from app.services.users import UsersServiceDep
from app.utils.validation import flatten_validation_error

router = APIRouter(prefix="/live-trades", tags=["live-trades"])


class LiveTradesQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    trading_account_id: str | None = Field(default=None, min_length=1, alias="tradingAccountId")


def parse_live_trades_query(
    trading_account_id: str | None = Query(None, alias="tradingAccountId"),
) -> LiveTradesQuery:
    try:
        return LiveTradesQuery.model_validate({"tradingAccountId": trading_account_id})
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=flatten_validation_error(exc),
        ) from exc


@router.get("")
async def list_live_trades(
    clerk_user: CurrentClerkUser,
    query: Annotated[LiveTradesQuery, Depends(parse_live_trades_query)],
    users_service: UsersServiceDep,
    live_trades_service: LiveTradesServiceDep,
):
    user = await users_service.find_by_clerk_user_id(clerk_user.clerk_user_id)
    if user is None:
        user = await users_service.find_or_create_by_clerk_user_id(clerk_user.clerk_user_id)

    data = await live_trades_service.get_live_trades_for_user(
        user.id,
        query.model_dump(by_alias=True),
    )
    return {"data": data}
