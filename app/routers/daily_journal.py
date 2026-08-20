from fastapi import APIRouter, Query, Request

from app.dependencies.services import CurrentUser, DailyJournalServiceDep
from app.schemas.common import DataEnvelope
from app.schemas.daily_journal import (
    DailyJournalInput,
    DailyJournalResponse,
    ListDailyJournalQuery,
    UpdateDailyJournalInput,
)
from app.utils.validation import parse_body

router = APIRouter(prefix="/daily-journal", tags=["daily-journal"])


@router.get("")
async def list_daily_journal_entries(
    current_user: CurrentUser,
    daily_journal_service: DailyJournalServiceDep,
    trading_account_id: str | None = Query(None, alias="tradingAccountId"),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
) -> DataEnvelope[list[DailyJournalResponse]]:
    query_payload = {
        key: value
        for key, value in {
            "tradingAccountId": trading_account_id,
            "from": from_date,
            "to": to_date,
        }.items()
        if value is not None
    }
    parsed = parse_body(ListDailyJournalQuery, query_payload)
    data = await daily_journal_service.list_for_user(
        current_user.id,
        parsed,  # type: ignore[arg-type]
    )
    return DataEnvelope(data=data)


@router.get("/{journal_id}")
async def get_daily_journal_entry(
    journal_id: str,
    current_user: CurrentUser,
    daily_journal_service: DailyJournalServiceDep,
) -> DataEnvelope[DailyJournalResponse]:
    journal = await daily_journal_service.find_by_id_for_user(journal_id, current_user.id)
    return DataEnvelope(data=daily_journal_service.to_response(journal))


@router.post("")
async def create_daily_journal_entry(
    request: Request,
    current_user: CurrentUser,
    daily_journal_service: DailyJournalServiceDep,
) -> DataEnvelope[DailyJournalResponse]:
    body = await request.json()
    parsed = parse_body(DailyJournalInput, body)
    data = await daily_journal_service.create_for_user(
        current_user.id,
        parsed,  # type: ignore[arg-type]
    )
    return DataEnvelope(data=data)


@router.patch("/{journal_id}")
async def update_daily_journal_entry(
    journal_id: str,
    request: Request,
    current_user: CurrentUser,
    daily_journal_service: DailyJournalServiceDep,
) -> DataEnvelope[DailyJournalResponse]:
    body = await request.json()
    parsed = parse_body(UpdateDailyJournalInput, body)
    data = await daily_journal_service.update_for_user(
        journal_id,
        current_user.id,
        parsed,  # type: ignore[arg-type]
    )
    return DataEnvelope(data=data)
