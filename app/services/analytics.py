from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.calculators.analytics import (
    HeatmapMetric,
    build_calendar,
    build_equity_curve,
    build_heatmap,
    calculate_drawdown,
    calculate_net_pnl,
    calculate_streaks,
    compare_periods,
    discover_edge_combinations,
    get_trading_session,
    get_zoned_date_parts,
    resolve_comparison_windows,
    summarize_after_loss_buckets,
    summarize_after_losses_performance,
    summarize_after_win_buckets,
    summarize_by_instrument,
    summarize_by_strategy,
    summarize_closed_trades,
    summarize_concentration,
    summarize_direction_by_instrument,
    summarize_duration_analytics,
    summarize_early_winner_exits,
    summarize_execution_analytics,
    summarize_insights_analytics,
    summarize_mistake_analytics,
    summarize_overall_direction,
    summarize_period_metrics,
    summarize_planned_rr_analytics,
    summarize_planned_vs_realized,
    summarize_plan_compliance,
    summarize_psychology_analytics,
    summarize_risk_stats,
    summarize_rolling_performance,
    summarize_tag_analytics,
    summarize_time_analytics,
    to_edge_finder_trade,
)
from app.calculators.analytics.group_performance import (
    AnalyticsTradeRecord,
    ClosedTradeSummaryInput,
    GroupedPerformance,
)
from app.calculators.analytics.plan_compliance import PlanComplianceStatus
from app.calculators.analytics.trade_metrics import TradeMetricsGroup
from app.dependencies.database import DbSession
from app.models.enums import (
    PlanComplianceStatus as ModelPlanComplianceStatus,
    TradeDirection,
    TradeStatus,
)
from app.models.models import (
    Trade,
    TradeMistake,
    TradeReview,
    TradeStrategy,
    TradeTag,
    User,
)
from app.schemas.analytics import AnalyticsQuery, PeriodComparisonQuery
from app.services.accounts import AccountsService, AccountsServiceDep

BASE_TRADE_LOAD_OPTIONS = (
    selectinload(Trade.trading_account),
    selectinload(Trade.trade_strategies).selectinload(TradeStrategy.strategy),
    selectinload(Trade.trade_tags).selectinload(TradeTag.tag),
    selectinload(Trade.trade_mistakes).selectinload(TradeMistake.mistake),
    selectinload(Trade.review),
)


class AnalyticsService:
    def __init__(self, db: AsyncSession, accounts_service: AccountsService) -> None:
        self._db = db
        self._accounts_service = accounts_service

    async def get_summary_for_user(self, user_id: str, query: AnalyticsQuery) -> dict[str, Any]:
        loaded = await self.load_trades(user_id, query)
        closed_trades = loaded["closed_trades"]
        open_trades = loaded["open_trades"]
        starting_balance = loaded["starting_balance"]
        current_balance = loaded["current_balance"]
        currency = loaded["currency"]

        closed_records = [self._to_summary_record(trade) for trade in closed_trades]
        summary = summarize_closed_trades(closed_records)
        equity_curve = build_equity_curve(
            [
                {
                    "closed_at": trade.closed_at,
                    "opened_at": trade.opened_at,
                    "net_pnl": self._to_float(trade.net_pnl),
                    "realized_r": self._to_float(trade.realized_r),
                }
                for trade in closed_trades
                if trade.closed_at is not None
            ],
            starting_balance,
        )
        drawdown = calculate_drawdown(equity_curve, starting_balance)
        streaks = calculate_streaks(
            [
                {
                    "net_pnl": self._to_float(trade.net_pnl),
                    "closed_at": trade.closed_at,
                }
                for trade in closed_trades
                if trade.closed_at is not None
            ]
        )
        calendar = build_calendar(
            [
                {
                    "closed_at": trade.closed_at,
                    "net_pnl": self._to_float(trade.net_pnl),
                    "realized_r": self._to_float(trade.realized_r),
                }
                for trade in closed_trades
                if trade.closed_at is not None
            ]
        )

        open_risk = sum(
            self._to_float(trade.initial_risk_amount) or 0.0 for trade in open_trades
        )
        realized_net_pnl = summary["net_pnl"]
        account_pnl = current_balance - starting_balance
        unrealized_pnl = account_pnl - realized_net_pnl
        has_synced_balance = starting_balance > 0 and current_balance > 0
        return_percentage = None
        if starting_balance > 0:
            if has_synced_balance:
                return_percentage = (account_pnl / starting_balance) * 100
            else:
                return_percentage = (realized_net_pnl / starting_balance) * 100

        return {
            "currency": currency,
            "tradeCount": len(closed_trades) + len(open_trades),
            "closedTradeCount": len(closed_trades),
            "openTradeCount": len(open_trades),
            "netPnl": self._format_number(realized_net_pnl),
            "accountPnl": self._format_number(account_pnl),
            "unrealizedPnl": self._format_number(unrealized_pnl),
            "grossProfit": self._format_number(summary["gross_profit"]),
            "grossLoss": self._format_number(summary["gross_loss"]),
            "returnPercentage": (
                None if return_percentage is None else self._format_number(return_percentage)
            ),
            "winCount": summary["win_count"],
            "lossCount": summary["loss_count"],
            "breakevenCount": summary["breakeven_count"],
            "winRate": (
                None
                if summary["win_rate"] is None
                else self._format_number(summary["win_rate"] * 100)
            ),
            "lossRate": (
                None
                if summary["loss_rate"] is None
                else self._format_number(summary["loss_rate"] * 100)
            ),
            "breakevenRate": (
                None
                if summary["breakeven_rate"] is None
                else self._format_number(summary["breakeven_rate"] * 100)
            ),
            "profitFactor": (
                None
                if summary["profit_factor"] is None
                else self._format_number(summary["profit_factor"])
            ),
            "moneyExpectancy": (
                None
                if summary["money_expectancy"] is None
                else self._format_number(summary["money_expectancy"])
            ),
            "rExpectancy": (
                None
                if summary["r_expectancy"] is None
                else self._format_number(summary["r_expectancy"])
            ),
            "totalR": (
                None if summary["total_r"] is None else self._format_number(summary["total_r"])
            ),
            "averageR": (
                None
                if summary["average_r"] is None
                else self._format_number(summary["average_r"])
            ),
            "averageWinner": (
                None
                if summary["average_winner"] is None
                else self._format_number(summary["average_winner"])
            ),
            "averageLoser": (
                None
                if summary["average_loser"] is None
                else self._format_number(summary["average_loser"])
            ),
            "averageWinLossRatio": (
                None
                if summary["average_win_loss_ratio"] is None
                else self._format_number(summary["average_win_loss_ratio"])
            ),
            "largestWinner": (
                None
                if summary["largest_winner"] is None
                else self._format_number(summary["largest_winner"])
            ),
            "largestLoser": (
                None
                if summary["largest_loser"] is None
                else self._format_number(summary["largest_loser"])
            ),
            "averageHoldingTimeMinutes": (
                None
                if summary["average_holding_time_minutes"] is None
                else self._format_number(summary["average_holding_time_minutes"])
            ),
            "medianHoldingTimeMinutes": (
                None
                if summary["median_holding_time_minutes"] is None
                else self._format_number(summary["median_holding_time_minutes"])
            ),
            "totalCommission": self._format_number(summary["total_commission"]),
            "totalSwap": self._format_number(summary["total_swap"]),
            "totalFees": self._format_number(summary["total_fees"]),
            "totalTradingCosts": self._format_number(summary["total_trading_costs"]),
            "maxDrawdownAmount": self._format_number(drawdown["max_drawdown_amount"]),
            "maxDrawdownPercentage": self._format_number(drawdown["max_drawdown_percentage"]),
            "currentDrawdownAmount": self._format_number(drawdown["current_drawdown_amount"]),
            "currentDrawdownPercentage": self._format_number(
                drawdown["current_drawdown_percentage"]
            ),
            "longestWinningStreak": streaks["longest_winning_streak"],
            "longestLosingStreak": streaks["longest_losing_streak"],
            "currentWinningStreak": streaks["current_winning_streak"],
            "currentLosingStreak": streaks["current_losing_streak"],
            "startingBalance": self._format_number(starting_balance),
            "currentBalance": self._format_number(current_balance),
            "currentOpenRisk": self._format_number(open_risk),
            "sampleConfidence": summary["sample_confidence"],
            "equityCurve": [
                {
                    "date": point["date"],
                    "balance": self._format_number(point["balance"]),
                    "cumulativePnl": self._format_number(point["cumulative_pnl"]),
                    "cumulativeR": self._format_number(point["cumulative_r"]),
                }
                for point in equity_curve
            ],
            "calendar": [
                {
                    "date": day["date"],
                    "pnl": self._format_number(day["pnl"]),
                    "r": self._format_number(day["r"]),
                    "tradeCount": day["trade_count"],
                }
                for day in calendar
            ],
        }

    async def get_instrument_performance_for_user(
        self, user_id: str, query: AnalyticsQuery
    ) -> list[dict[str, Any]]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        records = [self._to_record(trade) for trade in closed_trades]
        groups = summarize_by_instrument(records)

        return [
            {"symbol": group["label"], **self._format_grouped_performance(group)}
            for group in groups
        ]

    async def get_strategy_performance_for_user(
        self, user_id: str, query: AnalyticsQuery
    ) -> list[dict[str, Any]]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        records = [self._to_record(trade) for trade in closed_trades]
        groups = summarize_by_strategy(records)

        return [
            {
                "strategyId": None if group["key"] == "unassigned" else group["key"],
                "strategyName": group["label"],
                **self._format_grouped_performance(group),
            }
            for group in groups
        ]

    async def get_direction_analytics_for_user(
        self, user_id: str, query: AnalyticsQuery
    ) -> dict[str, Any]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        records = [self._to_direction_record(trade) for trade in closed_trades]
        overall = summarize_overall_direction(records)
        by_instrument = summarize_direction_by_instrument(records)

        return {
            "overall": [self._format_direction_side(side) for side in overall],
            "byInstrument": [
                {
                    "symbol": entry["symbol"],
                    "long": self._format_direction_side(entry["long"])
                    if entry["long"]
                    else None,
                    "short": self._format_direction_side(entry["short"])
                    if entry["short"]
                    else None,
                }
                for entry in by_instrument
            ],
        }

    async def get_behavior_analytics_for_user(
        self, user_id: str, query: AnalyticsQuery
    ) -> dict[str, Any]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        streak_trades = [
            {
                "net_pnl": self._to_float(trade.net_pnl),
                "realized_r": self._to_float(trade.realized_r),
                "closed_at": trade.closed_at,
            }
            for trade in closed_trades
            if trade.closed_at is not None
        ]

        after_losses = summarize_after_losses_performance(streak_trades)
        early_winner_exit = summarize_early_winner_exits(
            [
                {
                    "net_pnl": self._to_float(trade.net_pnl),
                    "realized_r": self._to_float(trade.realized_r),
                    "planned_rr": self._to_float(trade.planned_rr),
                }
                for trade in closed_trades
            ]
        )

        return {
            "afterLossBuckets": [
                self._format_metrics_group(group)
                for group in summarize_after_loss_buckets(streak_trades)
            ],
            "afterWinBuckets": [
                self._format_metrics_group(group)
                for group in summarize_after_win_buckets(streak_trades)
            ],
            "afterLossesComparison": {
                "lossStreakThreshold": after_losses["loss_streak_threshold"],
                "tradeCount": after_losses["trade_count"],
                "netPnl": self._format_number(after_losses["net_pnl"]),
                "winRate": (
                    None
                    if after_losses["win_rate"] is None
                    else self._format_number(after_losses["win_rate"] * 100)
                ),
                "averageR": (
                    None
                    if after_losses["average_r"] is None
                    else self._format_number(after_losses["average_r"])
                ),
                "rExpectancy": (
                    None
                    if after_losses["r_expectancy"] is None
                    else self._format_number(after_losses["r_expectancy"])
                ),
                "sampleConfidence": after_losses["sample_confidence"],
                "baselineTradeCount": after_losses["baseline_trade_count"],
                "baselineWinRate": (
                    None
                    if after_losses["baseline_win_rate"] is None
                    else self._format_number(after_losses["baseline_win_rate"] * 100)
                ),
                "baselineNetPnl": self._format_number(after_losses["baseline_net_pnl"]),
            },
            "earlyWinnerExit": {
                "winnerCount": early_winner_exit["winner_count"],
                "earlyExitCount": early_winner_exit["early_exit_count"],
                "earlyExitRate": (
                    None
                    if early_winner_exit["early_exit_rate"] is None
                    else self._format_number(early_winner_exit["early_exit_rate"] * 100)
                ),
                "averagePlannedR": (
                    None
                    if early_winner_exit["average_planned_r"] is None
                    else self._format_number(early_winner_exit["average_planned_r"])
                ),
                "averageRealizedR": (
                    None
                    if early_winner_exit["average_realized_r"] is None
                    else self._format_number(early_winner_exit["average_realized_r"])
                ),
                "averageCaptureRatio": (
                    None
                    if early_winner_exit["average_capture_ratio"] is None
                    else self._format_number(early_winner_exit["average_capture_ratio"] * 100)
                ),
                "sampleConfidence": early_winner_exit["sample_confidence"],
            },
        }

    async def get_plan_compliance_for_user(
        self, user_id: str, query: AnalyticsQuery
    ) -> list[dict[str, Any]]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        groups = summarize_plan_compliance(
            [
                {
                    "net_pnl": self._to_float(trade.net_pnl),
                    "realized_r": self._to_float(trade.realized_r),
                    "plan_compliance": self._plan_compliance_value(trade),
                }
                for trade in closed_trades
            ]
        )

        return [self._format_compliance_group(group) for group in groups]

    async def get_risk_stats_for_user(
        self, user_id: str, query: AnalyticsQuery
    ) -> list[dict[str, Any]]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        groups = summarize_risk_stats(
            [
                {
                    "net_pnl": self._to_float(trade.net_pnl),
                    "realized_r": self._to_float(trade.realized_r),
                    "initial_risk_percentage": self._to_float(trade.initial_risk_percentage),
                }
                for trade in closed_trades
            ]
        )

        return [self._format_risk_group(group) for group in groups]

    async def get_session_performance_for_user(
        self, user_id: str, query: AnalyticsQuery, timezone: str
    ) -> list[dict[str, Any]]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        analytics = summarize_time_analytics(
            [self._to_time_trade(trade) for trade in closed_trades],
            timezone,
        )

        return [
            {
                "session": group["key"],
                "sessionLabel": group["label"],
                **{
                    key: value
                    for key, value in self._format_metrics_group(group).items()
                    if key not in {"key", "label"}
                },
            }
            for group in analytics["sessions"]
        ]

    async def get_time_analytics_for_user(
        self, user_id: str, query: AnalyticsQuery, timezone: str
    ) -> dict[str, Any]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        analytics = summarize_time_analytics(
            [self._to_time_trade(trade) for trade in closed_trades],
            timezone,
        )

        return {
            "hours": [self._format_metrics_group(group) for group in analytics["hours"]],
            "twoHourWindows": [
                self._format_metrics_group(group) for group in analytics["two_hour_windows"]
            ],
            "daysOfWeek": [
                self._format_metrics_group(group) for group in analytics["days_of_week"]
            ],
            "months": [self._format_metrics_group(group) for group in analytics["months"]],
            "sessions": [
                self._format_metrics_group(group) for group in analytics["sessions"]
            ],
        }

    async def get_insights_for_user(
        self, user_id: str, query: AnalyticsQuery, timezone: str
    ) -> dict[str, Any]:
        closed_trades = (
            await self.load_trades(user_id, query, include_insights_fields=True)
        )["closed_trades"]
        insights = summarize_insights_analytics(
            [self._to_insights_trade(trade) for trade in closed_trades],
            timezone,
        )
        highlights = insights["highlights"]

        return {
            "highlights": {
                "bestHour": self._format_optional_metrics_group(highlights["best_hour"]),
                "worstHour": self._format_optional_metrics_group(highlights["worst_hour"]),
                "bestSession": self._format_optional_metrics_group(highlights["best_session"]),
                "worstSession": self._format_optional_metrics_group(highlights["worst_session"]),
                "bestDayOfWeek": self._format_optional_metrics_group(
                    highlights["best_day_of_week"]
                ),
                "worstDayOfWeek": self._format_optional_metrics_group(
                    highlights["worst_day_of_week"]
                ),
                "bestSymbol": self._format_optional_metrics_group(highlights["best_symbol"]),
                "worstSymbol": self._format_optional_metrics_group(highlights["worst_symbol"]),
                "bestTimeframe": self._format_optional_metrics_group(
                    highlights["best_timeframe"]
                ),
                "worstTimeframe": self._format_optional_metrics_group(
                    highlights["worst_timeframe"]
                ),
            },
            "sessionSymbols": [
                {
                    "session": row["session"],
                    "sessionLabel": row["session_label"],
                    "symbol": row["symbol"],
                    "tradeCount": row["trade_count"],
                    "netPnl": self._format_number(row["net_pnl"]),
                    "totalR": (
                        None if row["total_r"] is None else self._format_number(row["total_r"])
                    ),
                    "winRate": (
                        None
                        if row["win_rate"] is None
                        else self._format_number(row["win_rate"] * 100)
                    ),
                    "averageR": (
                        None
                        if row["average_r"] is None
                        else self._format_number(row["average_r"])
                    ),
                    "sampleConfidence": row["sample_confidence"],
                }
                for row in insights["session_symbols"]
            ],
            "timeframes": [
                self._format_metrics_group(group) for group in insights["timeframes"]
            ],
            "timeframeOutcomes": [
                {
                    "key": row["key"],
                    "label": row["label"],
                    "wins": row["wins"],
                    "losses": row["losses"],
                    "breakeven": row["breakeven"],
                    "winRate": (
                        None
                        if row["win_rate"] is None
                        else self._format_number(row["win_rate"] * 100)
                    ),
                    "netPnl": self._format_number(row["net_pnl"]),
                    "tradeCount": row["trade_count"],
                }
                for row in insights["timeframe_outcomes"]
            ],
            "journalCoverage": self._format_journal_coverage(insights["journal_coverage"]),
            "planComplianceByTimeframe": [
                {
                    "key": row["key"],
                    "label": row["label"],
                    "followed": row["followed"],
                    "partiallyFollowed": row["partially_followed"],
                    "didNotFollow": row["did_not_follow"],
                    "notReviewed": row["not_reviewed"],
                    "followedWinRate": (
                        None
                        if row["followed_win_rate"] is None
                        else self._format_number(row["followed_win_rate"] * 100)
                    ),
                    "notFollowedWinRate": (
                        None
                        if row["not_followed_win_rate"] is None
                        else self._format_number(row["not_followed_win_rate"] * 100)
                    ),
                }
                for row in insights["plan_compliance_by_timeframe"]
            ],
            "winningEntryCriteria": [
                self._format_metrics_group(group)
                for group in insights["winning_entry_criteria"]
            ],
            "losingEntryCriteria": [
                self._format_metrics_group(group)
                for group in insights["losing_entry_criteria"]
            ],
            "winningStrategies": [
                self._format_metrics_group(group) for group in insights["winning_strategies"]
            ],
            "losingStrategies": [
                self._format_metrics_group(group) for group in insights["losing_strategies"]
            ],
            "losingMistakes": [
                self._format_metrics_group(group) for group in insights["losing_mistakes"]
            ],
        }

    async def get_psychology_analytics_for_user(
        self, user_id: str, query: AnalyticsQuery
    ) -> dict[str, Any]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        analytics = summarize_psychology_analytics(
            [
                {
                    "net_pnl": self._to_float(trade.net_pnl),
                    "realized_r": self._to_float(trade.realized_r),
                    "pre_trade_emotion": (
                        trade.review.pre_trade_emotion.value
                        if trade.review and trade.review.pre_trade_emotion
                        else None
                    ),
                    "post_trade_emotion": (
                        trade.review.post_trade_emotion.value
                        if trade.review and trade.review.post_trade_emotion
                        else None
                    ),
                    "confidence_score": trade.review.confidence_score if trade.review else None,
                    "market_bias": (
                        trade.review.market_bias.value
                        if trade.review and trade.review.market_bias
                        else None
                    ),
                    "direction": trade.direction.value,
                }
                for trade in closed_trades
            ]
        )

        return {
            "preTradeEmotions": [
                self._format_metrics_group(group) for group in analytics["pre_trade_emotions"]
            ],
            "postTradeEmotions": [
                self._format_metrics_group(group) for group in analytics["post_trade_emotions"]
            ],
            "confidence": [
                self._format_metrics_group(group) for group in analytics["confidence"]
            ],
            "marketBias": [
                self._format_metrics_group(group) for group in analytics["market_bias"]
            ],
            "biasAlignment": [
                self._format_metrics_group(group) for group in analytics["bias_alignment"]
            ],
        }

    async def get_tag_analytics_for_user(
        self, user_id: str, query: AnalyticsQuery
    ) -> list[dict[str, Any]]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        tag_trades = [
            {
                "tag_id": entry.tag.id,
                "tag_name": entry.tag.name,
                "net_pnl": self._to_float(trade.net_pnl),
                "realized_r": self._to_float(trade.realized_r),
            }
            for trade in closed_trades
            for entry in trade.trade_tags
        ]

        return [
            {
                "tagId": group["tag_id"],
                "tagName": group["tag_name"],
                "tradeCount": group["trade_count"],
                "netPnl": self._format_number(group["net_pnl"]),
                "totalR": (
                    None if group["total_r"] is None else self._format_number(group["total_r"])
                ),
                "averageR": (
                    None
                    if group["average_r"] is None
                    else self._format_number(group["average_r"])
                ),
                "winRate": (
                    None
                    if group["win_rate"] is None
                    else self._format_number(group["win_rate"] * 100)
                ),
                "moneyExpectancy": (
                    None
                    if group["money_expectancy"] is None
                    else self._format_number(group["money_expectancy"])
                ),
                "rExpectancy": (
                    None
                    if group["r_expectancy"] is None
                    else self._format_number(group["r_expectancy"])
                ),
                "profitFactor": (
                    None
                    if group["profit_factor"] is None
                    else self._format_number(group["profit_factor"])
                ),
                "sampleConfidence": group["sample_confidence"],
            }
            for group in summarize_tag_analytics(tag_trades)
        ]

    async def get_mistake_analytics_for_user(
        self, user_id: str, query: AnalyticsQuery
    ) -> list[dict[str, Any]]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        mistake_trades = [
            {
                "mistake_id": entry.mistake.id,
                "mistake_name": entry.mistake.name,
                "net_pnl": self._to_float(trade.net_pnl),
                "realized_r": self._to_float(trade.realized_r),
            }
            for trade in closed_trades
            for entry in trade.trade_mistakes
        ]

        return [
            {
                "mistakeId": group["mistake_id"],
                "mistakeName": group["mistake_name"],
                "tradeCount": group["trade_count"],
                "netPnl": self._format_number(group["net_pnl"]),
                "totalR": (
                    None if group["total_r"] is None else self._format_number(group["total_r"])
                ),
                "averageR": (
                    None
                    if group["average_r"] is None
                    else self._format_number(group["average_r"])
                ),
                "winRate": (
                    None
                    if group["win_rate"] is None
                    else self._format_number(group["win_rate"] * 100)
                ),
                "moneyExpectancy": (
                    None
                    if group["money_expectancy"] is None
                    else self._format_number(group["money_expectancy"])
                ),
                "rExpectancy": (
                    None
                    if group["r_expectancy"] is None
                    else self._format_number(group["r_expectancy"])
                ),
                "profitFactor": (
                    None
                    if group["profit_factor"] is None
                    else self._format_number(group["profit_factor"])
                ),
                "sampleConfidence": group["sample_confidence"],
            }
            for group in summarize_mistake_analytics(mistake_trades)
        ]

    async def get_after_losses_analytics_for_user(
        self,
        user_id: str,
        query: AnalyticsQuery,
        loss_streak_threshold: int = 2,
    ) -> dict[str, Any]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        summary = summarize_after_losses_performance(
            [
                {
                    "net_pnl": self._to_float(trade.net_pnl),
                    "realized_r": self._to_float(trade.realized_r),
                    "closed_at": trade.closed_at,
                }
                for trade in closed_trades
                if trade.closed_at is not None
            ],
            loss_streak_threshold,
        )

        return {
            "lossStreakThreshold": summary["loss_streak_threshold"],
            "tradeCount": summary["trade_count"],
            "netPnl": self._format_number(summary["net_pnl"]),
            "winRate": (
                None
                if summary["win_rate"] is None
                else self._format_number(summary["win_rate"] * 100)
            ),
            "averageR": (
                None
                if summary["average_r"] is None
                else self._format_number(summary["average_r"])
            ),
            "rExpectancy": (
                None
                if summary["r_expectancy"] is None
                else self._format_number(summary["r_expectancy"])
            ),
            "sampleConfidence": summary["sample_confidence"],
            "baselineTradeCount": summary["baseline_trade_count"],
            "baselineWinRate": (
                None
                if summary["baseline_win_rate"] is None
                else self._format_number(summary["baseline_win_rate"] * 100)
            ),
            "baselineNetPnl": self._format_number(summary["baseline_net_pnl"]),
        }

    async def get_early_winner_exit_analytics_for_user(
        self, user_id: str, query: AnalyticsQuery
    ) -> dict[str, Any]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        summary = summarize_early_winner_exits(
            [
                {
                    "net_pnl": self._to_float(trade.net_pnl),
                    "realized_r": self._to_float(trade.realized_r),
                    "planned_rr": self._to_float(trade.planned_rr),
                }
                for trade in closed_trades
            ]
        )

        return {
            "winnerCount": summary["winner_count"],
            "earlyExitCount": summary["early_exit_count"],
            "earlyExitRate": (
                None
                if summary["early_exit_rate"] is None
                else self._format_number(summary["early_exit_rate"] * 100)
            ),
            "averagePlannedR": (
                None
                if summary["average_planned_r"] is None
                else self._format_number(summary["average_planned_r"])
            ),
            "averageRealizedR": (
                None
                if summary["average_realized_r"] is None
                else self._format_number(summary["average_realized_r"])
            ),
            "averageCaptureRatio": (
                None
                if summary["average_capture_ratio"] is None
                else self._format_number(summary["average_capture_ratio"] * 100)
            ),
            "sampleConfidence": summary["sample_confidence"],
        }

    async def get_heatmap_for_user(
        self,
        user_id: str,
        query: AnalyticsQuery,
        timezone: str,
        metric: HeatmapMetric,
    ) -> dict[str, Any]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        cells = build_heatmap(
            [self._to_time_trade(trade) for trade in closed_trades],
            timezone,
            metric,
        )
        return {
            "metric": metric,
            "cells": [
                {
                    "dayOfWeek": cell["day_of_week"],
                    "hour": cell["hour"],
                    "tradeCount": cell["trade_count"],
                    "netPnl": self._format_number(cell["net_pnl"]),
                    "averageR": (
                        None
                        if cell["average_r"] is None
                        else self._format_number(cell["average_r"])
                    ),
                    "winRate": (
                        None
                        if cell["win_rate"] is None
                        else self._format_number(cell["win_rate"] * 100)
                    ),
                    "value": self._format_number(cell["value"]),
                }
                for cell in cells
            ],
        }

    async def get_planned_rr_analytics_for_user(
        self, user_id: str, query: AnalyticsQuery
    ) -> dict[str, Any]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        trades = [
            {
                "net_pnl": self._to_float(trade.net_pnl) or 0.0,
                "realized_r": self._to_float(trade.realized_r),
                "planned_rr": self._to_float(trade.planned_rr),
            }
            for trade in closed_trades
        ]
        buckets = summarize_planned_rr_analytics(trades)
        summary = summarize_planned_vs_realized(trades)
        return {
            "buckets": [self._format_metrics_group(group) for group in buckets],
            "summary": {
                "tradeCount": summary["trade_count"],
                "averagePlannedR": (
                    None
                    if summary["average_planned_r"] is None
                    else self._format_number(summary["average_planned_r"])
                ),
                "averageRealizedR": (
                    None
                    if summary["average_realized_r"] is None
                    else self._format_number(summary["average_realized_r"])
                ),
                "averageRealizedWinnerR": (
                    None
                    if summary["average_realized_winner_r"] is None
                    else self._format_number(summary["average_realized_winner_r"])
                ),
                "targetAchievementRate": (
                    None
                    if summary["target_achievement_rate"] is None
                    else self._format_number(summary["target_achievement_rate"] * 100)
                ),
            },
        }

    async def get_duration_analytics_for_user(
        self, user_id: str, query: AnalyticsQuery
    ) -> list[dict[str, Any]]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        groups = summarize_duration_analytics(
            [
                {
                    "net_pnl": self._to_float(trade.net_pnl) or 0.0,
                    "realized_r": self._to_float(trade.realized_r),
                    "opened_at": trade.opened_at,
                    "closed_at": trade.closed_at,
                }
                for trade in closed_trades
                if trade.closed_at is not None
            ]
        )
        return [self._format_metrics_group(group) for group in groups]

    async def get_rolling_performance_for_user(
        self, user_id: str, query: AnalyticsQuery
    ) -> dict[str, Any]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        rolling = summarize_rolling_performance(
            [
                self._to_rolling_trade(trade)
                for trade in closed_trades
                if trade.closed_at is not None
            ]
        )
        return {
            "windowSize": rolling["window_size"],
            "currentWindow": self._format_metrics_group(rolling["current_window"]),
            "previousWindow": self._format_metrics_group(rolling["previous_window"]),
            "points": [
                {
                    "index": point["index"],
                    "closedAt": point["closed_at"],
                    "netPnl": self._format_number(point["net_pnl"]),
                    "windowTradeCount": point["window_trade_count"],
                    "windowWinRate": (
                        None
                        if point["window_win_rate"] is None
                        else self._format_number(point["window_win_rate"] * 100)
                    ),
                    "windowAverageR": (
                        None
                        if point["window_average_r"] is None
                        else self._format_number(point["window_average_r"])
                    ),
                    "windowNetPnl": self._format_number(point["window_net_pnl"]),
                }
                for point in rolling["points"]
            ],
        }

    async def get_concentration_for_user(
        self, user_id: str, query: AnalyticsQuery
    ) -> dict[str, Any]:
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        concentration = summarize_concentration(
            [{"net_pnl": self._to_float(trade.net_pnl) or 0.0} for trade in closed_trades]
        )
        return {
            "profit": {
                "winnerCount": concentration["profit"]["winner_count"],
                "grossProfit": self._format_number(concentration["profit"]["gross_profit"]),
                "top1Percent": (
                    None
                    if concentration["profit"]["top1_percent"] is None
                    else self._format_number(concentration["profit"]["top1_percent"])
                ),
                "top3Percent": (
                    None
                    if concentration["profit"]["top3_percent"] is None
                    else self._format_number(concentration["profit"]["top3_percent"])
                ),
                "top5Percent": (
                    None
                    if concentration["profit"]["top5_percent"] is None
                    else self._format_number(concentration["profit"]["top5_percent"])
                ),
                "top10Percent": (
                    None
                    if concentration["profit"]["top10_percent"] is None
                    else self._format_number(concentration["profit"]["top10_percent"])
                ),
                "netPnlExcludingTop1": self._format_number(
                    concentration["profit"]["net_pnl_excluding_top1"]
                ),
                "netPnlExcludingTop3": self._format_number(
                    concentration["profit"]["net_pnl_excluding_top3"]
                ),
                "netPnlExcludingTop5": self._format_number(
                    concentration["profit"]["net_pnl_excluding_top5"]
                ),
            },
            "loss": {
                "loserCount": concentration["loss"]["loser_count"],
                "grossLoss": self._format_number(concentration["loss"]["gross_loss"]),
                "worst1Percent": (
                    None
                    if concentration["loss"]["worst1_percent"] is None
                    else self._format_number(concentration["loss"]["worst1_percent"])
                ),
                "worst3Percent": (
                    None
                    if concentration["loss"]["worst3_percent"] is None
                    else self._format_number(concentration["loss"]["worst3_percent"])
                ),
                "worst5Percent": (
                    None
                    if concentration["loss"]["worst5_percent"] is None
                    else self._format_number(concentration["loss"]["worst5_percent"])
                ),
                "worst10Percent": (
                    None
                    if concentration["loss"]["worst10_percent"] is None
                    else self._format_number(concentration["loss"]["worst10_percent"])
                ),
            },
        }

    async def get_execution_analytics_for_user(
        self, user_id: str, query: AnalyticsQuery
    ) -> dict[str, Any]:
        closed_trades = (
            await self.load_trades(user_id, query, include_execution_details=True)
        )["closed_trades"]
        summary = summarize_execution_analytics(
            [
                {
                    "average_entry_price": self._to_float(trade.average_entry_price) or 0.0,
                    "average_exit_price": self._to_float(trade.average_exit_price),
                    "opened_at": trade.opened_at,
                    "closed_at": trade.closed_at,
                    "direction": trade.direction.value,
                    "initial_stop_loss": self._to_float(trade.initial_stop_loss),
                    "planned_rr": self._to_float(trade.planned_rr),
                    "realized_r": self._to_float(trade.realized_r),
                    "mfe_r": self._to_float(trade.mfe_r),
                    "entry_count": sum(
                        1 for execution in trade.executions if execution.type.value == "ENTRY"
                    ),
                    "exit_count": sum(
                        1 for execution in trade.executions if execution.type.value == "EXIT"
                    ),
                    "partial_exit_count": sum(
                        1 for event in trade.events if event.type.value == "PARTIAL_CLOSE"
                    ),
                    "events": [
                        {
                            "type": event.type.value,
                            "previous_value": event.previous_value,
                            "new_value": event.new_value,
                        }
                        for event in trade.events
                    ],
                }
                for trade in closed_trades
            ]
        )
        return {
            "tradeCount": summary["trade_count"],
            "averageEntryPrice": (
                None
                if summary["average_entry_price"] is None
                else self._format_number(summary["average_entry_price"], 5)
            ),
            "averageExitPrice": (
                None
                if summary["average_exit_price"] is None
                else self._format_number(summary["average_exit_price"], 5)
            ),
            "entryCount": summary["entry_count"],
            "exitCount": summary["exit_count"],
            "partialExitCount": summary["partial_exit_count"],
            "averageHoldTimeMinutes": (
                None
                if summary["average_hold_time_minutes"] is None
                else self._format_number(summary["average_hold_time_minutes"])
            ),
            "plannedVsRealized": {
                "tradeCount": summary["planned_vs_realized"]["trade_count"],
                "averagePlannedR": (
                    None
                    if summary["planned_vs_realized"]["average_planned_r"] is None
                    else self._format_number(summary["planned_vs_realized"]["average_planned_r"])
                ),
                "averageRealizedR": (
                    None
                    if summary["planned_vs_realized"]["average_realized_r"] is None
                    else self._format_number(summary["planned_vs_realized"]["average_realized_r"])
                ),
                "averageRealizedWinnerR": (
                    None
                    if summary["planned_vs_realized"]["average_realized_winner_r"] is None
                    else self._format_number(
                        summary["planned_vs_realized"]["average_realized_winner_r"]
                    )
                ),
                "targetAchievementRate": (
                    None
                    if summary["planned_vs_realized"]["target_achievement_rate"] is None
                    else self._format_number(
                        summary["planned_vs_realized"]["target_achievement_rate"] * 100
                    )
                ),
            },
            "slModificationCount": summary["sl_modification_count"],
            "tpModificationCount": summary["tp_modification_count"],
            "movedToBreakevenCount": summary["moved_to_breakeven_count"],
            "widenedSlCount": summary["widened_sl_count"],
            "reducedRiskCount": summary["reduced_risk_count"],
            "increasedRiskCount": summary["increased_risk_count"],
            "mfeAvailableCount": summary["mfe_available_count"],
            "averageExitEfficiency": (
                None
                if summary["average_exit_efficiency"] is None
                else self._format_number(summary["average_exit_efficiency"] * 100)
            ),
        }

    async def get_edge_finder_for_user(
        self, user_id: str, query: AnalyticsQuery
    ) -> dict[str, Any]:
        timezone = await self._get_user_timezone(user_id)
        closed_trades = (await self.load_trades(user_id, query))["closed_trades"]
        edge_trades = [
            to_edge_finder_trade(
                {
                    "symbol": trade.symbol,
                    "direction": trade.direction.value,
                    "strategy_names": [
                        entry.strategy.name for entry in trade.trade_strategies
                    ],
                    "session": get_trading_session(
                        get_zoned_date_parts(trade.opened_at, timezone)["hour"]
                    ),
                    "tag_names": [entry.tag.name for entry in trade.trade_tags],
                    "initial_risk_percentage": self._to_float(trade.initial_risk_percentage),
                    "plan_compliance": (
                        trade.review.plan_compliance.value
                        if trade.review and trade.review.plan_compliance
                        else None
                    ),
                    "net_pnl": self._to_float(trade.net_pnl) or 0.0,
                    "realized_r": self._to_float(trade.realized_r),
                }
            )
            for trade in closed_trades
        ]
        result = discover_edge_combinations(edge_trades)

        def format_combination(combination: dict[str, Any]) -> dict[str, Any]:
            return {
                "dimensions": combination["dimensions"],
                "tradeCount": combination["trade_count"],
                "netPnl": self._format_number(combination["net_pnl"]),
                "totalR": (
                    None
                    if combination["total_r"] is None
                    else self._format_number(combination["total_r"])
                ),
                "winRate": (
                    None
                    if combination["win_rate"] is None
                    else self._format_number(combination["win_rate"] * 100)
                ),
                "averageR": (
                    None
                    if combination["average_r"] is None
                    else self._format_number(combination["average_r"])
                ),
                "rExpectancy": (
                    None
                    if combination["r_expectancy"] is None
                    else self._format_number(combination["r_expectancy"])
                ),
                "profitFactor": (
                    None
                    if combination["profit_factor"] is None
                    else self._format_number(combination["profit_factor"])
                ),
                "sampleConfidence": combination["sample_confidence"],
            }

        return {
            "minimumSampleSize": result["minimum_sample_size"],
            "evaluatedCombinationCount": result["evaluated_combination_count"],
            "strongest": [format_combination(item) for item in result["strongest"]],
            "weakest": [format_combination(item) for item in result["weakest"]],
        }

    async def get_period_comparison_for_user(
        self, user_id: str, query: PeriodComparisonQuery
    ) -> dict[str, Any]:
        loaded = await self.load_trades(user_id, query)
        closed_trades = loaded["closed_trades"]
        starting_balance = loaded["starting_balance"]

        rolling_trades = [
            self._to_rolling_trade(trade)
            for trade in closed_trades
            if trade.closed_at is not None
        ]

        try:
            windows = resolve_comparison_windows(
                rolling_trades,
                query.mode.value,
                {
                    "period_a_from": query.period_a_from,
                    "period_a_to": query.period_a_to,
                    "period_b_from": query.period_b_from,
                    "period_b_to": query.period_b_to,
                },
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error

        period_a = summarize_period_metrics(windows["period_a"], starting_balance)
        period_b = summarize_period_metrics(windows["period_b"], starting_balance)

        return {
            "mode": query.mode.value,
            "periodA": {
                "label": windows["period_a_label"],
                **self._format_period_metrics(period_a),
            },
            "periodB": {
                "label": windows["period_b_label"],
                **self._format_period_metrics(period_b),
            },
            "deltas": self._format_period_deltas(compare_periods(period_a, period_b)),
        }

    async def load_trades(
        self,
        user_id: str,
        query: AnalyticsQuery,
        *,
        include_execution_details: bool = False,
        include_insights_fields: bool = False,
    ) -> dict[str, Any]:
        if query.trading_account_id:
            await self._accounts_service.find_by_id_for_user(query.trading_account_id, user_id)

        filters = [
            Trade.user_id == user_id,
            Trade.status.in_([TradeStatus.OPEN, TradeStatus.CLOSED]),
        ]

        if query.trading_account_id:
            filters.append(Trade.trading_account_id == query.trading_account_id)
        if query.symbol:
            filters.append(Trade.symbol == query.symbol)
        if query.direction:
            filters.append(Trade.direction == TradeDirection(query.direction.value))
        if query.risk_min is not None:
            filters.append(Trade.initial_risk_percentage >= query.risk_min)
        if query.risk_max is not None:
            filters.append(Trade.initial_risk_percentage <= query.risk_max)
        if query.closed_from:
            filters.append(Trade.closed_at >= query.closed_from)
        if query.closed_to:
            filters.append(Trade.closed_at <= query.closed_to)

        if query.strategy_id:
            filters.append(
                exists(
                    select(1).where(
                        TradeStrategy.trade_id == Trade.id,
                        TradeStrategy.strategy_id == query.strategy_id,
                    )
                )
            )
        if query.tag_id:
            filters.append(
                exists(
                    select(1).where(
                        TradeTag.trade_id == Trade.id,
                        TradeTag.tag_id == query.tag_id,
                    )
                )
            )
        if query.mistake_id:
            filters.append(
                exists(
                    select(1).where(
                        TradeMistake.trade_id == Trade.id,
                        TradeMistake.mistake_id == query.mistake_id,
                    )
                )
            )

        review_conditions = self._build_review_filter(query)
        if review_conditions:
            filters.append(
                exists(
                    select(1).where(
                        TradeReview.trade_id == Trade.id,
                        *review_conditions,
                    )
                )
            )

        load_options = list(BASE_TRADE_LOAD_OPTIONS)
        if include_execution_details:
            load_options.extend(
                (
                    selectinload(Trade.executions),
                    selectinload(Trade.events),
                )
            )

        result = await self._db.execute(
            select(Trade)
            .options(*load_options)
            .where(*filters)
            .order_by(Trade.closed_at.asc())
        )
        trades = list(result.scalars().unique().all())

        closed_trades = [trade for trade in trades if trade.status == TradeStatus.CLOSED]
        open_trades = [trade for trade in trades if trade.status == TradeStatus.OPEN]

        if query.result is not None:
            if query.result.value == "WIN":
                closed_trades = [
                    trade for trade in closed_trades if self._to_float(trade.net_pnl) > 0
                ]
            elif query.result.value == "LOSS":
                closed_trades = [
                    trade for trade in closed_trades if self._to_float(trade.net_pnl) < 0
                ]
            elif query.result.value == "BREAKEVEN":
                closed_trades = [
                    trade for trade in closed_trades if self._to_float(trade.net_pnl) == 0
                ]

        if query.session is not None:
            timezone = await self._get_user_timezone(user_id)
            closed_trades = [
                trade
                for trade in closed_trades
                if get_trading_session(get_zoned_date_parts(trade.opened_at, timezone)["hour"])
                == query.session.value
            ]

        starting_balance = 0.0
        current_balance = 0.0
        currency = "USD"

        if query.trading_account_id:
            account = (
                closed_trades[0].trading_account
                if closed_trades
                else open_trades[0].trading_account
                if open_trades
                else await self._accounts_service.find_by_id_for_user(
                    query.trading_account_id,
                    user_id,
                )
            )
            starting_balance = self._to_float(account.starting_balance) or 0.0
            current_balance = self._to_float(account.current_balance) or 0.0
            currency = account.currency
        else:
            accounts = await self._accounts_service.list_for_user(user_id)
            starting_balance = sum(self._to_float(account.starting_balance) or 0.0 for account in accounts)
            current_balance = sum(self._to_float(account.current_balance) or 0.0 for account in accounts)
            currency = accounts[0].currency if accounts else "USD"

            if accounts and any(account.currency != currency for account in accounts):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Select a trading account to view analytics across mixed currencies.",
                )

        return {
            "closed_trades": closed_trades,
            "open_trades": open_trades,
            "starting_balance": starting_balance,
            "current_balance": current_balance,
            "currency": currency,
            "total_closed_pnl": calculate_net_pnl(
                [{"net_pnl": self._to_float(trade.net_pnl)} for trade in closed_trades]
            ),
        }

    def _build_review_filter(self, query: AnalyticsQuery) -> list[Any]:
        conditions: list[Any] = []

        if query.pre_trade_emotion:
            conditions.append(TradeReview.pre_trade_emotion == query.pre_trade_emotion.value)
        if query.post_trade_emotion:
            conditions.append(TradeReview.post_trade_emotion == query.post_trade_emotion.value)
        if query.plan_compliance:
            conditions.append(
                TradeReview.plan_compliance == ModelPlanComplianceStatus(query.plan_compliance.value)
            )
        elif query.followed_plan is True:
            conditions.append(
                TradeReview.plan_compliance == ModelPlanComplianceStatus.FOLLOWED
            )
        elif query.followed_plan is False:
            conditions.append(
                TradeReview.plan_compliance == ModelPlanComplianceStatus.DID_NOT_FOLLOW
            )
        if query.market_bias:
            conditions.append(TradeReview.market_bias == query.market_bias.value)
        if query.confidence_min is not None:
            conditions.append(TradeReview.confidence_score >= query.confidence_min)
        if query.confidence_max is not None:
            conditions.append(TradeReview.confidence_score <= query.confidence_max)

        return conditions

    async def _get_user_timezone(self, user_id: str) -> str:
        result = await self._db.execute(select(User.timezone).where(User.id == user_id))
        timezone = result.scalar_one_or_none()
        return timezone or "UTC"

    @staticmethod
    def _to_float(value: Decimal | float | int | None) -> float | None:
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _plan_compliance_value(trade: Trade) -> PlanComplianceStatus:
        if trade.review and trade.review.plan_compliance:
            return trade.review.plan_compliance.value  # type: ignore[return-value]
        return "NOT_REVIEWED"

    def _to_record(self, trade: Trade) -> AnalyticsTradeRecord:
        return {
            "symbol": trade.symbol,
            "strategies": [
                {"id": entry.strategy.id, "name": entry.strategy.name}
                for entry in trade.trade_strategies
            ],
            "direction": trade.direction.value,  # type: ignore[typeddict-item]
            "net_pnl": self._to_float(trade.net_pnl) or 0.0,
            "realized_r": self._to_float(trade.realized_r),
        }

    def _to_direction_record(self, trade: Trade) -> dict[str, Any]:
        return {
            "symbol": trade.symbol,
            "direction": trade.direction.value,
            "net_pnl": self._to_float(trade.net_pnl) or 0.0,
            "realized_r": self._to_float(trade.realized_r),
        }

    def _to_summary_record(self, trade: Trade) -> ClosedTradeSummaryInput:
        return {
            **self._to_record(trade),
            "commission": self._to_float(trade.commission) or 0.0,
            "swap": self._to_float(trade.swap) or 0.0,
            "fees": self._to_float(trade.fees) or 0.0,
            "opened_at": trade.opened_at,
            "closed_at": trade.closed_at,
        }

    def _to_rolling_trade(self, trade: Trade) -> dict[str, Any]:
        return {
            "net_pnl": self._to_float(trade.net_pnl) or 0.0,
            "realized_r": self._to_float(trade.realized_r),
            "closed_at": trade.closed_at,
            "opened_at": trade.opened_at,
            "has_mistake": len(trade.trade_mistakes) > 0,
            "plan_compliance": (
                trade.review.plan_compliance.value
                if trade.review and trade.review.plan_compliance
                else None
            ),
            "initial_risk_percentage": self._to_float(trade.initial_risk_percentage),
            "commission": self._to_float(trade.commission) or 0.0,
            "swap": self._to_float(trade.swap) or 0.0,
            "fees": self._to_float(trade.fees) or 0.0,
        }

    def _to_time_trade(self, trade: Trade) -> dict[str, Any]:
        return {
            "net_pnl": self._to_float(trade.net_pnl) or 0.0,
            "realized_r": self._to_float(trade.realized_r),
            "opened_at": trade.opened_at,
        }

    def _to_insights_trade(self, trade: Trade) -> dict[str, Any]:
        return {
            "net_pnl": self._to_float(trade.net_pnl) or 0.0,
            "realized_r": self._to_float(trade.realized_r),
            "symbol": trade.symbol,
            "opened_at": trade.opened_at,
            "chart_timeframe": trade.chart_timeframe.value if trade.chart_timeframe else None,
            "strategies": [
                {"id": entry.strategy.id, "name": entry.strategy.name}
                for entry in trade.trade_strategies
            ],
            "tags": [{"id": entry.tag.id, "name": entry.tag.name} for entry in trade.trade_tags],
            "mistakes": [
                {"id": entry.mistake.id, "name": entry.mistake.name}
                for entry in trade.trade_mistakes
            ],
            "review": (
                {
                    "plan_compliance": (
                        trade.review.plan_compliance.value if trade.review.plan_compliance else None
                    ),
                    "pre_trade_plan": trade.review.pre_trade_plan,
                    "post_trade_plan": trade.review.post_trade_plan,
                    "what_went_well": trade.review.what_went_well,
                    "what_went_wrong": trade.review.what_went_wrong,
                    "confidence_score": trade.review.confidence_score,
                }
                if trade.review
                else None
            ),
        }

    @staticmethod
    def _format_number(value: float, decimals: int = 2) -> str:
        return f"{value:.{decimals}f}"

    def _format_grouped_performance(self, group: GroupedPerformance) -> dict[str, Any]:
        return {
            "tradeCount": group["trade_count"],
            "netPnl": self._format_number(group["net_pnl"]),
            "grossProfit": self._format_number(group["gross_profit"]),
            "grossLoss": self._format_number(group["gross_loss"]),
            "totalR": (
                None if group["total_r"] is None else self._format_number(group["total_r"])
            ),
            "winRate": (
                None
                if group["win_rate"] is None
                else self._format_number(group["win_rate"] * 100)
            ),
            "averageR": (
                None
                if group["average_r"] is None
                else self._format_number(group["average_r"])
            ),
            "rExpectancy": (
                None
                if group["r_expectancy"] is None
                else self._format_number(group["r_expectancy"])
            ),
            "moneyExpectancy": (
                None
                if group["money_expectancy"] is None
                else self._format_number(group["money_expectancy"])
            ),
            "profitFactor": (
                None
                if group["profit_factor"] is None
                else self._format_number(group["profit_factor"])
            ),
            "longTradeCount": group["long_trade_count"],
            "shortTradeCount": group["short_trade_count"],
            "longNetPnl": self._format_number(group["long_net_pnl"]),
            "shortNetPnl": self._format_number(group["short_net_pnl"]),
            "sampleConfidence": group["sample_confidence"],
        }

    def _format_direction_side(self, side: dict[str, Any]) -> dict[str, Any]:
        return {
            "direction": side["direction"],
            "label": side["label"],
            "tradeCount": side["trade_count"],
            "netPnl": self._format_number(side["net_pnl"]),
            "totalR": (
                None if side["total_r"] is None else self._format_number(side["total_r"])
            ),
            "winRate": (
                None
                if side["win_rate"] is None
                else self._format_number(side["win_rate"] * 100)
            ),
            "averageR": (
                None
                if side["average_r"] is None
                else self._format_number(side["average_r"])
            ),
            "rExpectancy": (
                None
                if side["r_expectancy"] is None
                else self._format_number(side["r_expectancy"])
            ),
            "profitFactor": (
                None
                if side["profit_factor"] is None
                else self._format_number(side["profit_factor"])
            ),
            "sampleConfidence": side["sample_confidence"],
        }

    def _format_optional_metrics_group(
        self, group: TradeMetricsGroup | None
    ) -> dict[str, Any] | None:
        return self._format_metrics_group(group) if group else None

    def _format_metrics_group(self, group: TradeMetricsGroup) -> dict[str, Any]:
        return {
            "key": group["key"],
            "label": group["label"],
            "tradeCount": group["trade_count"],
            "netPnl": self._format_number(group["net_pnl"]),
            "totalR": (
                None if group["total_r"] is None else self._format_number(group["total_r"])
            ),
            "winRate": (
                None
                if group["win_rate"] is None
                else self._format_number(group["win_rate"] * 100)
            ),
            "averageR": (
                None
                if group["average_r"] is None
                else self._format_number(group["average_r"])
            ),
            "moneyExpectancy": (
                None
                if group["money_expectancy"] is None
                else self._format_number(group["money_expectancy"])
            ),
            "rExpectancy": (
                None
                if group["r_expectancy"] is None
                else self._format_number(group["r_expectancy"])
            ),
            "profitFactor": (
                None
                if group["profit_factor"] is None
                else self._format_number(group["profit_factor"])
            ),
            "sampleConfidence": group["sample_confidence"],
        }

    def _format_period_metrics(self, metrics: dict[str, Any]) -> dict[str, Any]:
        return {
            "tradeCount": metrics["trade_count"],
            "netPnl": self._format_number(metrics["net_pnl"]),
            "totalR": (
                None if metrics["total_r"] is None else self._format_number(metrics["total_r"])
            ),
            "winRate": (
                None
                if metrics["win_rate"] is None
                else self._format_number(metrics["win_rate"] * 100)
            ),
            "averageR": (
                None
                if metrics["average_r"] is None
                else self._format_number(metrics["average_r"])
            ),
            "moneyExpectancy": (
                None
                if metrics["money_expectancy"] is None
                else self._format_number(metrics["money_expectancy"])
            ),
            "profitFactor": (
                None
                if metrics["profit_factor"] is None
                else self._format_number(metrics["profit_factor"])
            ),
            "maxDrawdownAmount": self._format_number(metrics["max_drawdown_amount"]),
            "maxDrawdownPercentage": self._format_number(metrics["max_drawdown_percentage"]),
            "mistakeRate": (
                None
                if metrics["mistake_rate"] is None
                else self._format_number(metrics["mistake_rate"] * 100)
            ),
            "planComplianceRate": (
                None
                if metrics["plan_compliance_rate"] is None
                else self._format_number(metrics["plan_compliance_rate"] * 100)
            ),
            "averageRiskPercentage": (
                None
                if metrics["average_risk_percentage"] is None
                else self._format_number(metrics["average_risk_percentage"])
            ),
            "averageHoldingTimeMinutes": (
                None
                if metrics["average_holding_time_minutes"] is None
                else self._format_number(metrics["average_holding_time_minutes"])
            ),
            "totalTradingCosts": self._format_number(metrics["total_trading_costs"]),
            "sampleConfidence": metrics["sample_confidence"],
        }

    def _format_period_deltas(self, deltas: dict[str, Any]) -> dict[str, Any]:
        return {
            "netPnl": (
                None if deltas["net_pnl"] is None else self._format_number(deltas["net_pnl"])
            ),
            "winRate": (
                None
                if deltas["win_rate"] is None
                else self._format_number(deltas["win_rate"] * 100)
            ),
            "averageR": (
                None
                if deltas["average_r"] is None
                else self._format_number(deltas["average_r"])
            ),
            "moneyExpectancy": (
                None
                if deltas["money_expectancy"] is None
                else self._format_number(deltas["money_expectancy"])
            ),
            "profitFactor": (
                None
                if deltas["profit_factor"] is None
                else self._format_number(deltas["profit_factor"])
            ),
            "mistakeRate": (
                None
                if deltas["mistake_rate"] is None
                else self._format_number(deltas["mistake_rate"] * 100)
            ),
            "planComplianceRate": (
                None
                if deltas["plan_compliance_rate"] is None
                else self._format_number(deltas["plan_compliance_rate"] * 100)
            ),
            "maxDrawdownAmount": (
                None
                if deltas["max_drawdown_amount"] is None
                else self._format_number(deltas["max_drawdown_amount"])
            ),
            "maxDrawdownPercentage": (
                None
                if deltas["max_drawdown_percentage"] is None
                else self._format_number(deltas["max_drawdown_percentage"])
            ),
            "totalR": (
                None if deltas["total_r"] is None else self._format_number(deltas["total_r"])
            ),
            "averageRiskPercentage": (
                None
                if deltas["average_risk_percentage"] is None
                else self._format_number(deltas["average_risk_percentage"])
            ),
            "averageHoldingTimeMinutes": (
                None
                if deltas["average_holding_time_minutes"] is None
                else self._format_number(deltas["average_holding_time_minutes"])
            ),
            "totalTradingCosts": (
                None
                if deltas["total_trading_costs"] is None
                else self._format_number(deltas["total_trading_costs"])
            ),
        }

    def _format_compliance_group(self, group: dict[str, Any]) -> dict[str, Any]:
        return {
            "label": group["label"],
            "planCompliance": group["plan_compliance"],
            "tradeCount": group["trade_count"],
            "netPnl": self._format_number(group["net_pnl"]),
            "winRate": (
                None
                if group["win_rate"] is None
                else self._format_number(group["win_rate"] * 100)
            ),
            "averageR": (
                None
                if group["average_r"] is None
                else self._format_number(group["average_r"])
            ),
            "moneyExpectancy": (
                None
                if group["money_expectancy"] is None
                else self._format_number(group["money_expectancy"])
            ),
            "rExpectancy": (
                None
                if group["r_expectancy"] is None
                else self._format_number(group["r_expectancy"])
            ),
            "profitFactor": (
                None
                if group["profit_factor"] is None
                else self._format_number(group["profit_factor"])
            ),
            "sampleConfidence": group["sample_confidence"],
        }

    def _format_risk_group(self, group: dict[str, Any]) -> dict[str, Any]:
        return {
            "label": group["label"],
            "riskPercentageMin": (
                None
                if group["risk_percentage_min"] is None
                else self._format_number(group["risk_percentage_min"])
            ),
            "riskPercentageMax": (
                None
                if group["risk_percentage_max"] is None
                else self._format_number(group["risk_percentage_max"])
            ),
            "tradeCount": group["trade_count"],
            "netPnl": self._format_number(group["net_pnl"]),
            "winRate": (
                None
                if group["win_rate"] is None
                else self._format_number(group["win_rate"] * 100)
            ),
            "averageR": (
                None
                if group["average_r"] is None
                else self._format_number(group["average_r"])
            ),
            "moneyExpectancy": (
                None
                if group["money_expectancy"] is None
                else self._format_number(group["money_expectancy"])
            ),
            "rExpectancy": (
                None
                if group["r_expectancy"] is None
                else self._format_number(group["r_expectancy"])
            ),
            "profitFactor": (
                None
                if group["profit_factor"] is None
                else self._format_number(group["profit_factor"])
            ),
            "sampleConfidence": group["sample_confidence"],
        }

    @staticmethod
    def _format_journal_coverage(coverage: dict[str, Any]) -> dict[str, Any]:
        return {
            "closedTrades": coverage["closed_trades"],
            "withChartTimeframe": coverage["with_chart_timeframe"],
            "withPreTradePlan": coverage["with_pre_trade_plan"],
            "withPostTradePlan": coverage["with_post_trade_plan"],
            "withWhatWentWell": coverage["with_what_went_well"],
            "withWhatWentWrong": coverage["with_what_went_wrong"],
            "withPlanCompliance": coverage["with_plan_compliance"],
            "withEntryCriteria": coverage["with_entry_criteria"],
            "withStrategies": coverage["with_strategies"],
            "withMistakesTagged": coverage["with_mistakes_tagged"],
        }


async def get_analytics_service(
    db: DbSession,
    accounts_service: AccountsServiceDep,
) -> AnalyticsService:
    return AnalyticsService(db, accounts_service)


AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]
