from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.dependencies.rate_limit import rate_limit
from app.dependencies.services import CurrentUser, UploadsServiceDep
from app.models.enums import ScreenshotType

router = APIRouter(prefix="/trades/{trade_id}/screenshots", tags=["uploads"])


@router.get("")
async def list_screenshots(
    user: CurrentUser,
    trade_id: str,
    uploads_service: UploadsServiceDep,
):
    data = await uploads_service.list_screenshots_for_trade(trade_id, user.id)
    return {"data": data}


@router.post("", dependencies=[Depends(rate_limit(30, 60_000))])
async def upload_screenshot(
    user: CurrentUser,
    trade_id: str,
    uploads_service: UploadsServiceDep,
    file: UploadFile = File(...),
    screenshot_type: ScreenshotType = Form(ScreenshotType.BEFORE_TRADE, alias="type"),
):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Screenshot file is required.",
        )

    buffer = await file.read()
    data = await uploads_service.upload_screenshot_for_trade(
        trade_id,
        user.id,
        screenshot_type=screenshot_type,
        file_name=file.filename,
        mime_type=file.content_type or "application/octet-stream",
        buffer=buffer,
    )
    return {"data": data}


@router.delete("/{screenshot_id}")
async def delete_screenshot(
    user: CurrentUser,
    trade_id: str,
    screenshot_id: str,
    uploads_service: UploadsServiceDep,
):
    data = await uploads_service.delete_screenshot_for_trade(
        trade_id,
        screenshot_id,
        user.id,
    )
    return {"data": data}
