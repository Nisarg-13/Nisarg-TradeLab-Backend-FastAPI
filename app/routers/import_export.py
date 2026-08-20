from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.dependencies.auth import CurrentClerkUser
from app.dependencies.rate_limit import rate_limit
from app.schemas.import_export import (
    CsvImportCommitInput,
    CsvImportPreviewInput,
    ExportQuery,
)
from app.services.import_export import ImportExportServiceDep
from app.services.users import UsersServiceDep
from app.utils.validation import flatten_validation_error, parse_body

router = APIRouter(tags=["import-export"])


def parse_export_query(
    trading_account_id: str | None = Query(None, alias="tradingAccountId"),
) -> ExportQuery:
    try:
        return ExportQuery.model_validate({"tradingAccountId": trading_account_id})
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=flatten_validation_error(exc),
        ) from exc


@router.post(
    "/import/csv/preview",
    dependencies=[Depends(rate_limit(20, 60_000))],
)
async def preview_csv_import(
    request: Request,
    clerk_user: CurrentClerkUser,
    users_service: UsersServiceDep,
    import_export_service: ImportExportServiceDep,
):
    body = await request.json()
    parsed = parse_body(CsvImportPreviewInput, body)
    user = await users_service.find_or_create_by_clerk_user_id(clerk_user.clerk_user_id)
    data = await import_export_service.preview_csv_import(user.id, parsed)  # type: ignore[arg-type]
    return {"data": data}


@router.post(
    "/import/csv",
    dependencies=[Depends(rate_limit(10, 60_000))],
)
async def commit_csv_import(
    request: Request,
    clerk_user: CurrentClerkUser,
    users_service: UsersServiceDep,
    import_export_service: ImportExportServiceDep,
):
    body = await request.json()
    parsed = parse_body(CsvImportCommitInput, body)
    user = await users_service.find_or_create_by_clerk_user_id(clerk_user.clerk_user_id)
    data = await import_export_service.commit_csv_import(user.id, parsed)  # type: ignore[arg-type]
    return {"data": data}


@router.get(
    "/export/csv",
    dependencies=[Depends(rate_limit(20, 60_000))],
)
async def export_csv(
    clerk_user: CurrentClerkUser,
    query: Annotated[ExportQuery, Depends(parse_export_query)],
    users_service: UsersServiceDep,
    import_export_service: ImportExportServiceDep,
):
    user = await users_service.find_or_create_by_clerk_user_id(clerk_user.clerk_user_id)
    data = await import_export_service.export_trades_csv(user.id, query)
    return JSONResponse(content={"data": data}, headers={"Content-Type": "text/csv"})


@router.get(
    "/export/json",
    dependencies=[Depends(rate_limit(20, 60_000))],
)
async def export_json(
    clerk_user: CurrentClerkUser,
    query: Annotated[ExportQuery, Depends(parse_export_query)],
    users_service: UsersServiceDep,
    import_export_service: ImportExportServiceDep,
):
    user = await users_service.find_or_create_by_clerk_user_id(clerk_user.clerk_user_id)
    data = await import_export_service.export_trades_json(user.id, query)
    return {"data": data}
