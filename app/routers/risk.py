from pydantic import ValidationError
from fastapi import APIRouter, HTTPException, Request, status

from app.dependencies.auth import CurrentClerkUser
from app.schemas.common import DataEnvelope
from app.schemas.risk import CalculateRiskBody, CalculateRiskResponse
from app.services.risk import RiskService
from app.utils.validation import flatten_validation_error

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/instruments")
async def list_risk_instruments(
    _clerk_user: CurrentClerkUser,
) -> DataEnvelope[list[dict[str, object]]]:
    return DataEnvelope(data=RiskService.list_instruments())


@router.post("/calculate")
async def calculate_risk(
    request: Request,
    _clerk_user: CurrentClerkUser,
) -> DataEnvelope[CalculateRiskResponse]:
    body = await request.json()
    try:
        parsed = CalculateRiskBody.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Invalid risk calculator input.",
                "details": flatten_validation_error(exc),
            },
        ) from exc

    return DataEnvelope(data=RiskService.calculate(parsed))
