from typing import Annotated

from fastapi import Depends

from app.config import Settings, get_settings
from app.dependencies.auth import CurrentUser
from app.dependencies.database import DbSession
from app.services.accounts import AccountsService, AccountsServiceDep, get_accounts_service
from app.services.analytics import AnalyticsService, AnalyticsServiceDep, get_analytics_service
from app.services.daily_journal import DailyJournalService
from app.services.instruments import InstrumentsService, InstrumentsServiceDep, get_instruments_service
from app.services.mistakes import MistakesService
from app.services.risk import RiskService
from app.services.strategies import StrategiesService
from app.services.tags import TagsService
from app.services.trades import TradesService
from app.services.uploads import UploadsService
from app.services.users import UsersService, UsersServiceDep


def get_strategies_service(db: DbSession) -> StrategiesService:
    return StrategiesService(db)


StrategiesServiceDep = Annotated[StrategiesService, Depends(get_strategies_service)]


def get_tags_service(db: DbSession) -> TagsService:
    return TagsService(db)


TagsServiceDep = Annotated[TagsService, Depends(get_tags_service)]


def get_mistakes_service(db: DbSession) -> MistakesService:
    return MistakesService(db)


MistakesServiceDep = Annotated[MistakesService, Depends(get_mistakes_service)]


def get_daily_journal_service(
    db: DbSession,
    accounts_service: AccountsServiceDep,
) -> DailyJournalService:
    return DailyJournalService(db, accounts_service)


DailyJournalServiceDep = Annotated[DailyJournalService, Depends(get_daily_journal_service)]


def get_risk_service() -> RiskService:
    return RiskService()


RiskServiceDep = Annotated[RiskService, Depends(get_risk_service)]


def get_trades_service(
    db: DbSession,
    accounts_service: AccountsServiceDep,
    instruments_service: InstrumentsServiceDep,
) -> TradesService:
    return TradesService(db, accounts_service, instruments_service)


TradesServiceDep = Annotated[TradesService, Depends(get_trades_service)]


def get_uploads_service(
    db: DbSession,
    trades_service: TradesServiceDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> UploadsService:
    return UploadsService(db, trades_service, settings)


UploadsServiceDep = Annotated[UploadsService, Depends(get_uploads_service)]


__all__ = [
    "AccountsServiceDep",
    "AnalyticsServiceDep",
    "CurrentUser",
    "DailyJournalServiceDep",
    "InstrumentsServiceDep",
    "MistakesServiceDep",
    "RiskServiceDep",
    "StrategiesServiceDep",
    "TagsServiceDep",
    "TradesServiceDep",
    "UploadsServiceDep",
    "UsersServiceDep",
    "get_accounts_service",
    "get_analytics_service",
    "get_trades_service",
    "get_uploads_service",
]
