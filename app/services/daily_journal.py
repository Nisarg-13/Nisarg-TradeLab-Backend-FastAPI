from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import DailyJournal
from app.schemas.daily_journal import (
    DailyJournalInput,
    DailyJournalResponse,
    ListDailyJournalQuery,
    UpdateDailyJournalInput,
)
from app.services.accounts import AccountsService
from app.utils.ids import generate_cuid
from app.utils.ownership import assert_resource_ownership


class DailyJournalService:
    def __init__(self, db: AsyncSession, accounts_service: AccountsService) -> None:
        self._db = db
        self._accounts_service = accounts_service

    async def list_for_user(
        self,
        user_id: str,
        query: ListDailyJournalQuery,
    ) -> list[DailyJournalResponse]:
        if query.trading_account_id:
            await self._accounts_service.find_by_id_for_user(query.trading_account_id, user_id)

        stmt = select(DailyJournal).where(DailyJournal.user_id == user_id)

        if query.trading_account_id:
            stmt = stmt.where(DailyJournal.trading_account_id == query.trading_account_id)
        if query.from_:
            stmt = stmt.where(DailyJournal.date >= query.from_)
        if query.to:
            stmt = stmt.where(DailyJournal.date <= query.to)

        stmt = stmt.order_by(DailyJournal.date.desc())
        result = await self._db.execute(stmt)
        journals = list(result.scalars().all())
        return [self.to_response(journal) for journal in journals]

    async def find_by_id_for_user(self, journal_id: str, user_id: str) -> DailyJournal:
        result = await self._db.execute(
            select(DailyJournal).where(DailyJournal.id == journal_id)
        )
        journal = result.scalar_one_or_none()

        if not journal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Daily journal entry not found",
            )

        assert_resource_ownership(journal.user_id, user_id)
        return journal

    async def create_for_user(
        self,
        user_id: str,
        input_data: DailyJournalInput,
    ) -> DailyJournalResponse:
        await self._accounts_service.find_by_id_for_user(
            input_data.trading_account_id,
            user_id,
        )

        journal = DailyJournal(
            id=generate_cuid(),
            user_id=user_id,
            trading_account_id=input_data.trading_account_id,
            date=self._to_date_only(input_data.date),
            confidence_score=input_data.confidence_score,
            market_bias=input_data.market_bias,
            pre_trade_plan=input_data.pre_trade_plan,
            post_trade_plan=input_data.post_trade_plan,
            what_went_well=input_data.what_went_well,
            what_went_wrong=input_data.what_went_wrong,
        )
        self._db.add(journal)
        await self._db.commit()
        await self._db.refresh(journal)
        return self.to_response(journal)

    async def update_for_user(
        self,
        journal_id: str,
        user_id: str,
        input_data: UpdateDailyJournalInput,
    ) -> DailyJournalResponse:
        journal = await self.find_by_id_for_user(journal_id, user_id)

        if input_data.confidence_score is not None:
            journal.confidence_score = input_data.confidence_score
        if input_data.market_bias is not None:
            journal.market_bias = input_data.market_bias
        if input_data.pre_trade_plan is not None:
            journal.pre_trade_plan = input_data.pre_trade_plan
        if input_data.post_trade_plan is not None:
            journal.post_trade_plan = input_data.post_trade_plan
        if input_data.what_went_well is not None:
            journal.what_went_well = input_data.what_went_well
        if input_data.what_went_wrong is not None:
            journal.what_went_wrong = input_data.what_went_wrong

        await self._db.commit()
        await self._db.refresh(journal)
        return self.to_response(journal)

    @staticmethod
    def to_response(journal: DailyJournal) -> DailyJournalResponse:
        return DailyJournalResponse(
            id=journal.id,
            tradingAccountId=journal.trading_account_id,
            date=journal.date.isoformat(),
            confidenceScore=journal.confidence_score,
            marketBias=journal.market_bias,
            preTradePlan=journal.pre_trade_plan,
            postTradePlan=journal.post_trade_plan,
            whatWentWell=journal.what_went_well,
            whatWentWrong=journal.what_went_wrong,
            createdAt=journal.created_at.isoformat(),
            updatedAt=journal.updated_at.isoformat(),
        )

    @staticmethod
    def _to_date_only(value: datetime | date) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value

        if value.tzinfo is None:
            return date(value.year, value.month, value.day)

        utc_value = value.astimezone(UTC)
        return date(utc_value.year, utc_value.month, utc_value.day)
