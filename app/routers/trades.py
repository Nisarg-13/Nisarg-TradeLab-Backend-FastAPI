from fastapi import APIRouter, Depends

from app.dependencies.services import CurrentUser, TradesServiceDep
from app.schemas.trade import (
    AddExecutionInput,
    BulkUpdateTradeJournalInput,
    CloseTradeInput,
    CreateTradeInput,
    ListTradesQuery,
    UpdateTradeInput,
    UpdateTradeReviewInput,
)
from app.services.trades import TradesService

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("")
async def list_trades(
    user: CurrentUser,
    trades_service: TradesServiceDep,
    query: ListTradesQuery = Depends(),
):
    return await trades_service.list_for_user(user.id, query)


@router.post("")
async def create_trade(
    user: CurrentUser,
    body: CreateTradeInput,
    trades_service: TradesServiceDep,
):
    trade = await trades_service.create_for_user(user.id, body)
    return {"data": trades_service.to_trade_response(trade)}


@router.patch("/bulk-journal")
async def bulk_update_journal(
    user: CurrentUser,
    body: BulkUpdateTradeJournalInput,
    trades_service: TradesServiceDep,
):
    return await trades_service.bulk_update_journal_for_user(user.id, body)


@router.get("/{trade_id}")
async def get_trade(
    user: CurrentUser,
    trade_id: str,
    trades_service: TradesServiceDep,
):
    trade = await trades_service.find_by_id_for_user(trade_id, user.id)
    return {"data": trades_service.to_trade_response(trade)}


@router.patch("/{trade_id}")
async def update_trade(
    user: CurrentUser,
    trade_id: str,
    body: UpdateTradeInput,
    trades_service: TradesServiceDep,
):
    trade = await trades_service.update_for_user(trade_id, user.id, body)
    return {"data": trades_service.to_trade_response(trade)}


@router.post("/{trade_id}/executions")
async def add_execution(
    user: CurrentUser,
    trade_id: str,
    body: AddExecutionInput,
    trades_service: TradesServiceDep,
):
    trade = await trades_service.add_execution_for_user(trade_id, user.id, body)
    return {"data": trades_service.to_trade_response(trade)}


@router.post("/{trade_id}/close")
async def close_trade(
    user: CurrentUser,
    trade_id: str,
    body: CloseTradeInput,
    trades_service: TradesServiceDep,
):
    trade = await trades_service.close_for_user(trade_id, user.id, body)
    return {"data": trades_service.to_trade_response(trade)}


@router.get("/{trade_id}/review")
async def get_review(
    user: CurrentUser,
    trade_id: str,
    trades_service: TradesServiceDep,
):
    review = await trades_service.get_review_for_user(trade_id, user.id)
    return {"data": trades_service.to_review_response(review)}


@router.patch("/{trade_id}/review")
async def update_review(
    user: CurrentUser,
    trade_id: str,
    body: UpdateTradeReviewInput,
    trades_service: TradesServiceDep,
):
    review = await trades_service.update_review_for_user(trade_id, user.id, body)
    return {"data": trades_service.to_review_response(review)}
