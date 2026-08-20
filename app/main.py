from datetime import UTC, datetime

from fastapi import FastAPI

from app.config import get_settings
from app.middleware.exceptions import register_exception_handlers
from app.routers import api_router
from app.utils.cors import configure_cors, parse_allowed_origins


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Nisarg TradeLab Backend")

    register_exception_handlers(app)

    allowed_origins = parse_allowed_origins(settings.FRONTEND_URL)
    configure_cors(app, allowed_origins)

    @app.get("/")
    async def get_root() -> dict[str, str]:
        return {
            "service": "nisarg-tradelab-backend",
            "status": "ok",
            "health": "/health",
            "api": "/api/v1",
        }

    @app.get("/health")
    async def get_health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "nisarg-tradelab-backend",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
