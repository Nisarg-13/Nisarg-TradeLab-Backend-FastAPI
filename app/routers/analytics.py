from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.services import AnalyticsServiceDep, CurrentUser
from app.schemas.analytics import AnalyticsQuery, HeatmapQuery, PeriodComparisonQuery

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
async def get_summary(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_summary_for_user(user.id, query)
    return {"data": data}


@router.get("/instruments")
async def get_instruments(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_instrument_performance_for_user(user.id, query)
    return {"data": data}


@router.get("/strategies")
async def get_strategies(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_strategy_performance_for_user(user.id, query)
    return {"data": data}


@router.get("/plan-compliance")
async def get_plan_compliance(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_plan_compliance_for_user(user.id, query)
    return {"data": data}


@router.get("/risk")
async def get_risk_stats(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_risk_stats_for_user(user.id, query)
    return {"data": data}


@router.get("/time")
async def get_time_analytics(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_time_analytics_for_user(user.id, query, user.timezone)
    return {"data": data}


@router.get("/heatmap")
async def get_heatmap(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: HeatmapQuery = Depends(),
):
    data = await analytics_service.get_heatmap_for_user(
        user.id, query, user.timezone, query.metric.value
    )
    return {"data": data}


@router.get("/psychology")
async def get_psychology(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_psychology_analytics_for_user(user.id, query)
    return {"data": data}


@router.get("/mistakes")
async def get_mistakes(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_mistake_analytics_for_user(user.id, query)
    return {"data": data}


@router.get("/tags")
async def get_tags(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_tag_analytics_for_user(user.id, query)
    return {"data": data}


@router.get("/planned-rr")
async def get_planned_rr(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_planned_rr_analytics_for_user(user.id, query)
    return {"data": data}


@router.get("/direction")
async def get_direction(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_direction_analytics_for_user(user.id, query)
    return {"data": data}


@router.get("/behavior")
async def get_behavior(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_behavior_analytics_for_user(user.id, query)
    return {"data": data}


@router.get("/duration")
async def get_duration(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_duration_analytics_for_user(user.id, query)
    return {"data": data}


@router.get("/rolling")
async def get_rolling(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_rolling_performance_for_user(user.id, query)
    return {"data": data}


@router.get("/period-comparison")
async def get_period_comparison(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: PeriodComparisonQuery = Depends(),
):
    try:
        data = await analytics_service.get_period_comparison_for_user(user.id, query)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return {"data": data}


@router.get("/concentration")
async def get_concentration(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_concentration_for_user(user.id, query)
    return {"data": data}


@router.get("/execution")
async def get_execution(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_execution_analytics_for_user(user.id, query)
    return {"data": data}


@router.get("/insights")
async def get_insights(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_insights_for_user(user.id, query, user.timezone)
    return {"data": data}


@router.get("/edge-finder")
async def get_edge_finder(
    user: CurrentUser,
    analytics_service: AnalyticsServiceDep,
    query: AnalyticsQuery = Depends(),
):
    data = await analytics_service.get_edge_finder_for_user(user.id, query)
    return {"data": data}
