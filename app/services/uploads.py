from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.enums import ScreenshotType
from app.models.models import TradeScreenshot
from app.services.trades import TradesService
from app.utils.ids import generate_cuid
from app.utils.ownership import assert_resource_ownership

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024


class UploadsService:
    def __init__(
        self,
        db: AsyncSession,
        trades_service: TradesService,
        settings: Settings,
    ) -> None:
        self._db = db
        self._trades_service = trades_service
        self._settings = settings

    async def list_screenshots_for_trade(
        self,
        trade_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        await self._trades_service.find_by_id_for_user(trade_id, user_id)

        result = await self._db.execute(
            select(TradeScreenshot)
            .where(TradeScreenshot.trade_id == trade_id, TradeScreenshot.user_id == user_id)
            .order_by(TradeScreenshot.created_at.desc())
        )
        screenshots = result.scalars().all()
        return [self._to_response(screenshot) for screenshot in screenshots]

    async def upload_screenshot_for_trade(
        self,
        trade_id: str,
        user_id: str,
        *,
        screenshot_type: ScreenshotType,
        file_name: str,
        mime_type: str,
        buffer: bytes,
    ) -> dict[str, Any]:
        trade = await self._trades_service.find_by_id_for_user(trade_id, user_id)

        if mime_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported screenshot file type.",
            )

        if len(buffer) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Screenshot exceeds the 5MB size limit.",
            )

        url = await self._upload_to_blob(
            f"trades/{trade.id}/{int(time.time() * 1000)}-{file_name}",
            buffer,
            mime_type,
        )

        screenshot = TradeScreenshot(
            id=generate_cuid(),
            trade_id=trade.id,
            user_id=user_id,
            type=screenshot_type,
            url=url,
            file_name=file_name,
            mime_type=mime_type,
            file_size=len(buffer),
        )
        self._db.add(screenshot)
        await self._db.commit()
        await self._db.refresh(screenshot)
        return self._to_response(screenshot)

    async def delete_screenshot_for_trade(
        self,
        trade_id: str,
        screenshot_id: str,
        user_id: str,
    ) -> dict[str, bool]:
        await self._trades_service.find_by_id_for_user(trade_id, user_id)

        result = await self._db.execute(
            select(TradeScreenshot).where(TradeScreenshot.id == screenshot_id)
        )
        screenshot = result.scalar_one_or_none()

        if not screenshot or screenshot.trade_id != trade_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Screenshot not found",
            )

        assert_resource_ownership(screenshot.user_id, user_id)

        await self._db.delete(screenshot)
        await self._db.commit()
        return {"deleted": True}

    async def _upload_to_blob(
        self,
        pathname: str,
        buffer: bytes,
        content_type: str,
    ) -> str:
        token = self._settings.BLOB_READ_WRITE_TOKEN
        if not token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Screenshot storage is not configured.",
            )

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"https://blob.vercel-storage.com/{quote(pathname, safe='')}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": content_type,
                    "x-api-version": "7",
                },
                content=buffer,
            )

        if not response.is_success:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to upload screenshot.",
            )

        payload = response.json()
        url = payload.get("url")
        if not url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Screenshot upload did not return a URL.",
            )
        return str(url)

    def _to_response(self, screenshot: TradeScreenshot) -> dict[str, Any]:
        return {
            "id": screenshot.id,
            "tradeId": screenshot.trade_id,
            "type": screenshot.type.value,
            "url": screenshot.url,
            "fileName": screenshot.file_name,
            "mimeType": screenshot.mime_type,
            "fileSize": screenshot.file_size,
            "createdAt": screenshot.created_at.isoformat(),
        }
