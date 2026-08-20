from fastapi import APIRouter

from app.routers import (
    accounts,
    ai,
    analytics,
    daily_journal,
    import_export,
    instruments,
    live_trades,
    mistakes,
    mt5,
    risk,
    strategies,
    tags,
    trades,
    uploads,
    users,
)

api_router = APIRouter()
api_router.include_router(accounts.router)
api_router.include_router(users.router)
api_router.include_router(trades.router)
api_router.include_router(uploads.router)
api_router.include_router(analytics.router)
api_router.include_router(risk.router)
api_router.include_router(strategies.router)
api_router.include_router(tags.router)
api_router.include_router(mistakes.router)
api_router.include_router(instruments.router)
api_router.include_router(daily_journal.router)
api_router.include_router(mt5.router)
api_router.include_router(live_trades.router)
api_router.include_router(import_export.router)
api_router.include_router(ai.router)
