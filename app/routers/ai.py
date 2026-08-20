from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError

from app.dependencies.auth import CurrentClerkUser
from app.dependencies.rate_limit import rate_limit
from app.schemas.ai import AiAnalysisQuery, AiChatInput
from app.services.ai import AiServiceDep
from app.services.users import UsersServiceDep
from app.utils.ai_coach_access import is_ai_coach_enabled
from app.utils.validation import flatten_validation_error, parse_body

router = APIRouter(prefix="/ai", tags=["ai"])


def parse_ai_analysis_query(
    trading_account_id: str | None = Query(None, alias="tradingAccountId"),
) -> AiAnalysisQuery:
    try:
        return AiAnalysisQuery.model_validate({"tradingAccountId": trading_account_id})
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=flatten_validation_error(exc),
        ) from exc


def assert_ai_coach_access(email: str | None) -> None:
    if not is_ai_coach_enabled(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "AI Coach is not available for your account yet. "
                "Stay tuned — this feature is rolling out soon."
            ),
        )


@router.get("/status")
async def get_status(
    clerk_user: CurrentClerkUser,
    users_service: UsersServiceDep,
    ai_service: AiServiceDep,
):
    await users_service.find_or_create_by_clerk_user_id(clerk_user.clerk_user_id)
    return {"data": ai_service.get_provider_status()}


@router.post(
    "/analysis",
    dependencies=[Depends(rate_limit(10, 60_000))],
)
async def generate_analysis(
    clerk_user: CurrentClerkUser,
    query: Annotated[AiAnalysisQuery, Depends(parse_ai_analysis_query)],
    users_service: UsersServiceDep,
    ai_service: AiServiceDep,
):
    user = await users_service.find_or_create_by_clerk_user_id(clerk_user.clerk_user_id)
    assert_ai_coach_access(user.email)
    data = await ai_service.generate_analysis_for_user(user.id, query)
    return {"data": data}


@router.get("/analysis")
async def list_analyses(
    clerk_user: CurrentClerkUser,
    users_service: UsersServiceDep,
    ai_service: AiServiceDep,
):
    user = await users_service.find_or_create_by_clerk_user_id(clerk_user.clerk_user_id)
    assert_ai_coach_access(user.email)
    data = await ai_service.list_analyses_for_user(user.id)
    return {"data": data}


@router.get("/analysis/{analysis_id}")
async def get_analysis(
    analysis_id: str,
    clerk_user: CurrentClerkUser,
    users_service: UsersServiceDep,
    ai_service: AiServiceDep,
):
    user = await users_service.find_or_create_by_clerk_user_id(clerk_user.clerk_user_id)
    assert_ai_coach_access(user.email)
    data = await ai_service.get_analysis_for_user(user.id, analysis_id)

    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )

    return {"data": data}


@router.post(
    "/chat",
    dependencies=[Depends(rate_limit(20, 60_000))],
)
async def ask_journal(
    request: Request,
    clerk_user: CurrentClerkUser,
    users_service: UsersServiceDep,
    ai_service: AiServiceDep,
):
    body = await request.json()
    parsed = parse_body(AiChatInput, body)
    user = await users_service.find_or_create_by_clerk_user_id(clerk_user.clerk_user_id)
    assert_ai_coach_access(user.email)
    data = await ai_service.ask_journal_for_user(user.id, parsed)  # type: ignore[arg-type]
    return {"data": data}


@router.get("/chat/history")
async def list_chat_history(
    clerk_user: CurrentClerkUser,
    users_service: UsersServiceDep,
    ai_service: AiServiceDep,
):
    user = await users_service.find_or_create_by_clerk_user_id(clerk_user.clerk_user_id)
    assert_ai_coach_access(user.email)
    data = await ai_service.list_chat_history_for_user(user.id)
    return {"data": data}
