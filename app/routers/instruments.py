from fastapi import APIRouter, Request

from app.dependencies.services import CurrentUser, InstrumentsServiceDep
from app.schemas.common import DataEnvelope
from app.schemas.instrument import (
    CreateInstrumentInput,
    InstrumentResponse,
    UpdateInstrumentInput,
)
from app.utils.validation import parse_body

router = APIRouter(prefix="/accounts/{account_id}/instruments", tags=["instruments"])


@router.get("")
async def list_instruments(
    account_id: str,
    current_user: CurrentUser,
    instruments_service: InstrumentsServiceDep,
) -> DataEnvelope[list[InstrumentResponse]]:
    instruments = await instruments_service.list_for_account(account_id, current_user.id)
    return DataEnvelope(
        data=[
            instruments_service.to_instrument_response(instrument)
            for instrument in instruments
        ]
    )


@router.post("")
async def create_instrument(
    account_id: str,
    request: Request,
    current_user: CurrentUser,
    instruments_service: InstrumentsServiceDep,
) -> DataEnvelope[InstrumentResponse]:
    body = await request.json()
    parsed = parse_body(CreateInstrumentInput, body)
    instrument = await instruments_service.create_for_account(
        account_id,
        current_user.id,
        parsed,  # type: ignore[arg-type]
    )
    return DataEnvelope(data=instruments_service.to_instrument_response(instrument))


@router.patch("/{instrument_id}")
async def update_instrument(
    account_id: str,
    instrument_id: str,
    request: Request,
    current_user: CurrentUser,
    instruments_service: InstrumentsServiceDep,
) -> DataEnvelope[InstrumentResponse]:
    body = await request.json()
    parsed = parse_body(UpdateInstrumentInput, body)
    instrument = await instruments_service.update_for_account(
        instrument_id,
        account_id,
        current_user.id,
        parsed,  # type: ignore[arg-type]
    )
    return DataEnvelope(data=instruments_service.to_instrument_response(instrument))
