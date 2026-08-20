from fastapi import APIRouter, Query, Request

from app.dependencies.services import AccountsServiceDep, CurrentUser
from app.schemas.account import (
    AccountResponse,
    CreateAccountInput,
    RiskSettingsResponse,
    UpdateAccountInput,
    UpdateRiskSettingsInput,
)
from app.schemas.common import DataEnvelope
from app.utils.validation import parse_body

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("")
async def list_accounts(
    current_user: CurrentUser,
    accounts_service: AccountsServiceDep,
    include_archived: str | None = Query(None, alias="includeArchived"),
) -> DataEnvelope[list[AccountResponse]]:
    accounts = await accounts_service.list_for_user(
        current_user.id,
        include_archived == "true",
    )
    return DataEnvelope(
        data=[accounts_service.to_account_response(account) for account in accounts]
    )


@router.post("")
async def create_account(
    request: Request,
    current_user: CurrentUser,
    accounts_service: AccountsServiceDep,
) -> DataEnvelope[AccountResponse]:
    body = await request.json()
    parsed = parse_body(CreateAccountInput, body)
    account = await accounts_service.create_for_user(current_user.id, parsed)  # type: ignore[arg-type]
    return DataEnvelope(data=accounts_service.to_account_response(account))


@router.get("/{account_id}")
async def get_account(
    account_id: str,
    current_user: CurrentUser,
    accounts_service: AccountsServiceDep,
) -> DataEnvelope[AccountResponse]:
    account = await accounts_service.find_by_id_for_user(account_id, current_user.id)
    return DataEnvelope(data=accounts_service.to_account_response(account))


@router.patch("/{account_id}")
async def update_account(
    account_id: str,
    request: Request,
    current_user: CurrentUser,
    accounts_service: AccountsServiceDep,
) -> DataEnvelope[AccountResponse]:
    body = await request.json()
    parsed = parse_body(UpdateAccountInput, body)
    account = await accounts_service.update_for_user(
        account_id,
        current_user.id,
        parsed,  # type: ignore[arg-type]
    )
    return DataEnvelope(data=accounts_service.to_account_response(account))


@router.post("/{account_id}/archive")
async def archive_account(
    account_id: str,
    current_user: CurrentUser,
    accounts_service: AccountsServiceDep,
) -> DataEnvelope[AccountResponse]:
    account = await accounts_service.archive_for_user(account_id, current_user.id)
    return DataEnvelope(data=accounts_service.to_account_response(account))


@router.get("/{account_id}/risk-settings")
async def get_risk_settings(
    account_id: str,
    current_user: CurrentUser,
    accounts_service: AccountsServiceDep,
) -> DataEnvelope[RiskSettingsResponse]:
    settings = await accounts_service.get_risk_settings(account_id, current_user.id)
    return DataEnvelope(data=accounts_service.to_risk_settings_response(settings))


@router.patch("/{account_id}/risk-settings")
async def update_risk_settings(
    account_id: str,
    request: Request,
    current_user: CurrentUser,
    accounts_service: AccountsServiceDep,
) -> DataEnvelope[RiskSettingsResponse]:
    body = await request.json()
    parsed = parse_body(UpdateRiskSettingsInput, body)
    settings = await accounts_service.update_risk_settings(
        account_id,
        current_user.id,
        parsed,  # type: ignore[arg-type]
    )
    return DataEnvelope(data=accounts_service.to_risk_settings_response(settings))
