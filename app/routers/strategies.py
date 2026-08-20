from fastapi import APIRouter, Request

from app.dependencies.services import CurrentUser, StrategiesServiceDep
from app.schemas.common import DataEnvelope
from app.schemas.strategy import (
    CreateStrategyInput,
    StrategyResponse,
    SuccessResponse,
    UpdateStrategyInput,
)
from app.utils.validation import parse_body

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("")
async def list_strategies(
    current_user: CurrentUser,
    strategies_service: StrategiesServiceDep,
) -> DataEnvelope[list[StrategyResponse]]:
    strategies = await strategies_service.list_for_user(current_user.id)
    return DataEnvelope(
        data=[
            strategies_service.to_strategy_response(strategy) for strategy in strategies
        ]
    )


@router.post("")
async def create_strategy(
    request: Request,
    current_user: CurrentUser,
    strategies_service: StrategiesServiceDep,
) -> DataEnvelope[StrategyResponse]:
    body = await request.json()
    parsed = parse_body(CreateStrategyInput, body)
    strategy = await strategies_service.create_for_user(
        current_user.id,
        parsed,  # type: ignore[arg-type]
    )
    return DataEnvelope(data=strategies_service.to_strategy_response(strategy))


@router.patch("/{strategy_id}")
async def update_strategy(
    strategy_id: str,
    request: Request,
    current_user: CurrentUser,
    strategies_service: StrategiesServiceDep,
) -> DataEnvelope[StrategyResponse]:
    body = await request.json()
    parsed = parse_body(UpdateStrategyInput, body)
    strategy = await strategies_service.update_for_user(
        strategy_id,
        current_user.id,
        parsed,  # type: ignore[arg-type]
    )
    return DataEnvelope(data=strategies_service.to_strategy_response(strategy))


@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: str,
    current_user: CurrentUser,
    strategies_service: StrategiesServiceDep,
) -> DataEnvelope[SuccessResponse]:
    await strategies_service.delete_for_user(strategy_id, current_user.id)
    return DataEnvelope(data=SuccessResponse(success=True))
