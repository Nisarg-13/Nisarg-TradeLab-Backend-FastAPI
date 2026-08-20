import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import ValidationError

from app.dependencies.auth import CurrentClerkUser
from app.dependencies.mt5_auth import Mt5ConnectionDep
from app.schemas.mt5 import (
    CreateMt5ConnectionInput,
    Mt5AccountSnapshotInput,
    Mt5ConnectInput,
    Mt5DealsInput,
    Mt5HeartbeatInput,
    Mt5InstrumentsInput,
    Mt5PositionLevelsInput,
    Mt5PositionsInput,
    Mt5ReconcileInput,
    Mt5TradeEventsInput,
    RecalculateImportedTradesInput,
)
from app.services.mt5_connection import Mt5ConnectionServiceDep
from app.services.mt5_live import Mt5LiveServiceDep
from app.services.mt5_sync import Mt5SyncServiceDep
from app.services.users import UsersServiceDep
from app.utils.validation import flatten_validation_error, parse_body

router = APIRouter(prefix="/mt5", tags=["mt5"])
logger = logging.getLogger(__name__)


@router.get("/connections")
async def list_connections(
    clerk_user: CurrentClerkUser,
    users_service: UsersServiceDep,
    mt5_connection_service: Mt5ConnectionServiceDep,
):
    user = await users_service.find_or_create_by_clerk_user_id(clerk_user.clerk_user_id)
    data = await mt5_connection_service.list_for_user(user.id)
    return {"data": data}


@router.post("/connections")
async def create_connection(
    request: Request,
    clerk_user: CurrentClerkUser,
    users_service: UsersServiceDep,
    mt5_connection_service: Mt5ConnectionServiceDep,
):
    body = await request.json()
    parsed = parse_body(CreateMt5ConnectionInput, body)
    user = await users_service.find_or_create_by_clerk_user_id(clerk_user.clerk_user_id)
    data = await mt5_connection_service.create_for_user(user.id, parsed)  # type: ignore[arg-type]
    return {"data": data}


@router.delete("/connections/{connection_id}")
async def revoke_connection(
    connection_id: str,
    clerk_user: CurrentClerkUser,
    users_service: UsersServiceDep,
    mt5_connection_service: Mt5ConnectionServiceDep,
):
    user = await users_service.find_or_create_by_clerk_user_id(clerk_user.clerk_user_id)
    data = await mt5_connection_service.revoke_for_user(connection_id, user.id)
    return {"data": data}


@router.post("/recalculate-trades")
async def recalculate_imported_trades(
    request: Request,
    clerk_user: CurrentClerkUser,
    users_service: UsersServiceDep,
    mt5_connection_service: Mt5ConnectionServiceDep,
    mt5_sync_service: Mt5SyncServiceDep,
):
    body = await request.json()
    try:
        parsed = RecalculateImportedTradesInput.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=flatten_validation_error(exc),
        ) from exc

    user = await users_service.find_or_create_by_clerk_user_id(clerk_user.clerk_user_id)
    connection = await mt5_connection_service.find_by_trading_account_for_user(
        parsed.trading_account_id,  # type: ignore[arg-type]
        user.id,
    )
    data = await mt5_sync_service.repair_imported_trades(connection.trading_account_id)
    return {"data": data}


@router.post("/connect")
async def connect(
    request: Request,
    connection: Mt5ConnectionDep,
    mt5_sync_service: Mt5SyncServiceDep,
):
    body = await request.json()
    parsed = parse_body(Mt5ConnectInput, body)
    data = await mt5_sync_service.connect(connection, parsed)  # type: ignore[arg-type]
    return {"data": data}


@router.post("/heartbeat")
async def heartbeat(
    request: Request,
    connection: Mt5ConnectionDep,
    mt5_sync_service: Mt5SyncServiceDep,
):
    body = await request.json()
    parsed = parse_body(Mt5HeartbeatInput, body or {})
    data = await mt5_sync_service.heartbeat(connection, parsed.ea_version)
    return {"data": data}


@router.post("/account")
async def account_snapshot(
    request: Request,
    connection: Mt5ConnectionDep,
    mt5_sync_service: Mt5SyncServiceDep,
):
    body = await request.json()
    parsed = parse_body(Mt5AccountSnapshotInput, body)
    data = await mt5_sync_service.sync_account_snapshot(connection, parsed)  # type: ignore[arg-type]
    return {"data": data}


@router.post("/instruments")
async def sync_instruments(
    request: Request,
    connection: Mt5ConnectionDep,
    mt5_sync_service: Mt5SyncServiceDep,
):
    body = await request.json()
    parsed = parse_body(Mt5InstrumentsInput, body)

    if not parsed.instruments:
        return {"data": {"imported": 0}}

    data = await mt5_sync_service.sync_instruments(connection, parsed.instruments)
    return {"data": data}


@router.post("/deals")
async def import_deals(
    request: Request,
    connection: Mt5ConnectionDep,
    mt5_sync_service: Mt5SyncServiceDep,
):
    body = await request.json()
    parsed = parse_body(Mt5DealsInput, body)
    data = await mt5_sync_service.import_deals(connection, parsed.deals)
    return {"data": data}


@router.post("/position-levels")
async def import_position_levels(
    request: Request,
    connection: Mt5ConnectionDep,
    mt5_sync_service: Mt5SyncServiceDep,
):
    body = await request.json()
    parsed = parse_body(Mt5PositionLevelsInput, body)

    if not parsed.levels:
        return {"data": {"updated": 0, "skipped": 0, "notFound": 0, "total": 0}}

    data = await mt5_sync_service.import_position_levels(connection, parsed.levels)
    return {"data": data}


@router.post("/positions")
async def sync_positions(
    request: Request,
    connection: Mt5ConnectionDep,
    mt5_live_service: Mt5LiveServiceDep,
):
    body = await request.json()
    parsed = parse_body(Mt5PositionsInput, body)
    logger.info(
        "MT5 position sync for connection %s: %s positions",
        connection.id,
        len(parsed.positions),
    )
    data = await mt5_live_service.sync_positions(connection, parsed.positions)
    return {"data": data}


@router.post("/events")
async def process_events(
    request: Request,
    connection: Mt5ConnectionDep,
    mt5_live_service: Mt5LiveServiceDep,
):
    body = await request.json()
    parsed = parse_body(Mt5TradeEventsInput, body)
    data = await mt5_live_service.process_events(connection, parsed.events)
    return {"data": data}


@router.post("/reconcile")
async def reconcile(
    request: Request,
    connection: Mt5ConnectionDep,
    mt5_live_service: Mt5LiveServiceDep,
):
    body = await request.json()
    parsed = parse_body(Mt5ReconcileInput, body)
    data = await mt5_live_service.reconcile(connection, parsed)  # type: ignore[arg-type]
    return {"data": data}
