from __future__ import annotations

from typing import Any

from app.schemas.ai import AiStructuredOutput

MetricRow = dict[str, Any]


def _as_number(value: str | int | float | None) -> float | None:
    if value is None:
        return None

    parsed = float(value) if not isinstance(value, (int, float)) else float(value)
    return parsed if parsed == parsed else None  # NaN check


def _read_numeric_field(source: Any, key: str) -> float | None:
    if not isinstance(source, dict):
        return None

    return _as_number(source.get(key))


def _read_string_field(source: Any, key: str, fallback: str = "n/a") -> str:
    if not isinstance(source, dict):
        return fallback

    value = source.get(key)

    if isinstance(value, (str, int, float)):
        return str(value)

    return fallback


def _is_record(value: Any) -> bool:
    return isinstance(value, dict)


def _format_pct(value: str | int | float | None) -> str | None:
    parsed = _as_number(value)
    return None if parsed is None else f"{parsed:.1f}%"


def _row_label(row: MetricRow) -> str:
    return str(
        row.get("label")
        or row.get("symbol")
        or row.get("name")
        or row.get("strategyName")
        or row.get("tagName")
        or row.get("mistakeName")
        or row.get("key")
        or "Unknown"
    )


def _coverage_gap(
    label: str,
    value: int | None,
    total: int | None,
    recommendation: str,
) -> str | None:
    if not total or total == 0 or value is None:
        return None

    ratio = value / total

    if ratio >= 0.6:
        return None

    return (
        f"{label}: only {value}/{total} trades ({round(ratio * 100)}%). {recommendation}"
    )


def _pick_metric_groups(source: Any) -> list[MetricRow]:
    if not source:
        return []

    if isinstance(source, list):
        return source

    if isinstance(source, dict):
        for bucket in (
            source.get("hours"),
            source.get("sessions"),
            source.get("daysOfWeek"),
            source.get("twoHourWindows"),
            source.get("overall"),
            source.get("byInstrument"),
        ):
            if isinstance(bucket, list) and bucket:
                return bucket

    return []


def _best_and_worst(rows: list[MetricRow]) -> dict[str, MetricRow | None]:
    eligible = [row for row in rows if (row.get("tradeCount") or 0) >= 1]

    if not eligible:
        return {"best": None, "worst": None}

    sorted_rows = sorted(
        eligible,
        key=lambda row: _as_number(row.get("netPnl")) or 0,
        reverse=True,
    )

    return {"best": sorted_rows[0], "worst": sorted_rows[-1]}


def build_data_driven_analysis(
    context: dict[str, Any],
    *,
    provider_label: str | None = None,
) -> AiStructuredOutput:
    sample_size = int(context.get("sampleSize") or 0)
    summary = context.get("summary") or {}
    currency = summary.get("currency") or "USD"

    if sample_size == 0:
        return AiStructuredOutput(
            summary=(
                "No closed trades yet. Start journaling closed trades with reviews, "
                "entry criteria, and chart timeframes to unlock personalized coaching."
            ),
            strengths=[],
            weaknesses=[],
            patterns=[],
            recommendations=[
                "Log every closed trade with at least one strategy and entry criterion tag.",
                "Add pre-trade plan and post-trade review on your next 10 trades.",
                "Set chart timeframe on each trade so timing analysis can identify your edge.",
            ],
            rules_for_next_trades=[
                "Do not increase position size until you have at least 20 reviewed closed trades.",
            ],
            data_limitations=[
                "Zero closed trades — all performance and coaching metrics are unavailable.",
            ],
        )

    strengths: list[str] = []
    weaknesses: list[str] = []
    patterns: list[str] = []
    recommendations: list[str] = []
    rules_for_next_trades: list[str] = []
    data_limitations: list[str] = []

    net_pnl = _as_number(summary.get("netPnl"))
    win_rate = _format_pct(summary.get("winRate"))
    profit_factor = _as_number(summary.get("profitFactor"))
    r_expectancy = _as_number(summary.get("rExpectancy"))
    money_expectancy = _as_number(summary.get("moneyExpectancy"))
    avg_winner = _as_number(summary.get("averageWinner"))
    avg_loser = _as_number(summary.get("averageLoser"))

    instruments = context.get("instruments") or []
    strategies = context.get("strategies") or []
    mistakes = context.get("mistakes") or []
    tags = context.get("tags") or []
    plan_compliance = context.get("planCompliance") or []
    insights = context.get("insights") or {}
    period_comparison = context.get("periodComparison") or {}
    behavior = context.get("behavior") or {}
    direction = context.get("direction") or {}

    instrument_extremes = _best_and_worst(instruments)
    best_instrument = instrument_extremes["best"]
    worst_instrument = instrument_extremes["worst"]

    time_sessions = _pick_metric_groups(context.get("timeAnalytics"))
    session_extremes = _best_and_worst(time_sessions)
    best_session = session_extremes["best"]
    worst_session = session_extremes["worst"]

    insight_highlights = insights.get("highlights") or {}
    journal_coverage = insights.get("journalCoverage") or {}
    session_symbols = insights.get("sessionSymbols") or []
    timeframe_outcomes = insights.get("timeframeOutcomes") or []

    if net_pnl is not None and net_pnl > 0:
        strengths.append(
            f"Overall net PnL is +{net_pnl:.2f} {currency}"
            + (f" with a {win_rate} win rate" if win_rate else "")
            + "."
        )
    elif net_pnl is not None and net_pnl < 0:
        weaknesses.append(
            f"Overall net PnL is {net_pnl:.2f} {currency}"
            + (f" with a {win_rate} win rate" if win_rate else "")
            + " — focus on cutting low-quality trades first."
        )

    if profit_factor is not None and profit_factor >= 1.5:
        strengths.append(
            f"Profit factor {profit_factor:.2f} shows winners are outpacing losers — "
            "protect this by keeping risk consistent."
        )
    elif profit_factor is not None and profit_factor < 1:
        weaknesses.append(
            f"Profit factor {profit_factor:.2f} is below 1.0 — average losses exceed average wins."
        )
        recommendations.append(
            "Improve win quality or tighten stops before adding new setups — expectancy is negative."
        )

    if r_expectancy is not None and r_expectancy > 0:
        strengths.append(f"Positive R expectancy ({r_expectancy:.2f}R per trade).")
    elif r_expectancy is not None and r_expectancy < 0:
        weaknesses.append(f"Negative R expectancy ({r_expectancy:.2f}R per trade).")

    if avg_winner is not None and avg_loser is not None and avg_loser != 0:
        ratio = abs(avg_winner / avg_loser)
        patterns.append(
            f"Average winner {avg_winner:.2f} {currency} vs average loser "
            f"{abs(avg_loser):.2f} {currency} ({ratio:.2f}:1 win/loss size ratio)."
        )

        if ratio < 1:
            weaknesses.append(
                "Losses are larger than winners on average — either cut losers faster "
                "or let winners run to planned targets."
            )
            rules_for_next_trades.append(
                "Cap loss size at your planned risk; do not widen stops after entry."
            )

    if best_instrument:
        strengths.append(
            f"Best instrument: {_row_label(best_instrument)} — net PnL {best_instrument.get('netPnl')} "
            f"across {best_instrument.get('tradeCount') or 0} trades"
            + (
                f" ({_format_pct(best_instrument.get('winRate'))} win rate)"
                if best_instrument.get("winRate") is not None
                else ""
            )
            + "."
        )
        recommendations.append(
            f"Allocate more focus to {_row_label(best_instrument)} during your best sessions "
            "while sample size remains meaningful."
        )

    if (
        worst_instrument
        and _as_number(worst_instrument.get("netPnl")) is not None
        and (_as_number(worst_instrument.get("netPnl")) or 0) < 0
    ):
        weaknesses.append(
            f"Worst instrument: {_row_label(worst_instrument)} — net PnL {worst_instrument.get('netPnl')} "
            f"over {worst_instrument.get('tradeCount') or 0} trades."
        )
        rules_for_next_trades.append(
            f"Reduce size or pause {_row_label(worst_instrument)} until you have a positive "
            "expectancy on at least 10 reviewed trades."
        )

    strategy_extremes = _best_and_worst(strategies)
    best_strategy = strategy_extremes["best"]
    worst_strategy = strategy_extremes["worst"]

    if best_strategy:
        strengths.append(
            f"Top strategy: {_row_label(best_strategy)} ({best_strategy.get('netPnl')} net PnL, "
            f"{best_strategy.get('tradeCount') or 0} trades)."
        )

    if (
        worst_strategy
        and _as_number(worst_strategy.get("netPnl")) is not None
        and (_as_number(worst_strategy.get("netPnl")) or 0) < 0
    ):
        weaknesses.append(
            f"Weakest strategy tag: {_row_label(worst_strategy)} ({worst_strategy.get('netPnl')} net PnL)."
        )

    tag_extremes = _best_and_worst(tags)
    best_tag = tag_extremes["best"]
    worst_tag = tag_extremes["worst"]

    if best_tag:
        strengths.append(
            f"Best entry criteria: {_row_label(best_tag)} — {best_tag.get('netPnl')} net PnL "
            f"across {best_tag.get('tradeCount') or 0} tagged trades."
        )

    if (
        worst_tag
        and _as_number(worst_tag.get("netPnl")) is not None
        and (_as_number(worst_tag.get("netPnl")) or 0) < 0
    ):
        weaknesses.append(
            f"Entry criteria to review: {_row_label(worst_tag)} — {worst_tag.get('netPnl')} net PnL."
        )

    if mistakes:
        top_mistake = sorted(
            mistakes,
            key=lambda row: row.get("tradeCount") or 0,
            reverse=True,
        )[0]

        if top_mistake:
            weaknesses.append(
                f"Most tagged mistake: {_row_label(top_mistake)} on {top_mistake.get('tradeCount') or 0} "
                f"trades ({top_mistake.get('netPnl')} net PnL when tagged)."
            )
            rules_for_next_trades.append(
                f'Pre-commit a rule to prevent "{_row_label(top_mistake)}" before the next session.'
            )

    followed_plan = next(
        (
            row
            for row in plan_compliance
            if row.get("planCompliance") == "FOLLOWED"
            or "followed" in _row_label(row).lower()
        ),
        None,
    )
    not_followed_plan = next(
        (
            row
            for row in plan_compliance
            if row.get("planCompliance") == "DID_NOT_FOLLOW"
            or "did not follow" in _row_label(row).lower()
        ),
        None,
    )

    if followed_plan and (followed_plan.get("tradeCount") or 0) > 0:
        strengths.append(
            f"Plan followed on {followed_plan.get('tradeCount')} trades ({followed_plan.get('netPnl')} net PnL"
            + (
                f", {_format_pct(followed_plan.get('winRate'))} win rate"
                if followed_plan.get("winRate") is not None
                else ""
            )
            + ")."
        )

    if not_followed_plan and (not_followed_plan.get("tradeCount") or 0) > 0:
        weaknesses.append(
            f"Plan not followed on {not_followed_plan.get('tradeCount')} trades "
            f"({not_followed_plan.get('netPnl')} net PnL) — discipline leak."
        )
        rules_for_next_trades.append(
            "If the setup is not in your written pre-trade plan, skip the trade."
        )

    session_highlight = insight_highlights.get("bestSession") or best_session
    session_weakness = insight_highlights.get("worstSession") or worst_session

    if session_highlight:
        strengths.append(
            f"Strongest session window: {_row_label(session_highlight)} "
            f"({session_highlight.get('netPnl')} net PnL)."
        )
        recommendations.append(
            f"Schedule high-conviction trades during {_row_label(session_highlight)} when possible."
        )

    if (
        session_weakness
        and _as_number(session_weakness.get("netPnl")) is not None
        and (_as_number(session_weakness.get("netPnl")) or 0) < 0
    ):
        weaknesses.append(
            f"Weakest session window: {_row_label(session_weakness)} "
            f"({session_weakness.get('netPnl')} net PnL)."
        )
        rules_for_next_trades.append(
            f"Cut position size by 50% or stop trading during {_row_label(session_weakness)} until reviewed."
        )

    if session_symbols:
        best_pair = sorted(
            session_symbols,
            key=lambda row: _as_number(row.get("netPnl")) or 0,
            reverse=True,
        )[0]
        worst_pair = sorted(
            session_symbols,
            key=lambda row: _as_number(row.get("netPnl")) or 0,
        )[0]

        if best_pair.get("sessionLabel") and best_pair.get("symbol"):
            patterns.append(
                f"Best session × pair: {best_pair['sessionLabel']} + {best_pair['symbol']} "
                f"({best_pair.get('netPnl')} net PnL)."
            )

        if (
            worst_pair.get("sessionLabel")
            and worst_pair.get("symbol")
            and (_as_number(worst_pair.get("netPnl")) or 0) < 0
        ):
            patterns.append(
                f"Worst session × pair: {worst_pair['sessionLabel']} + {worst_pair['symbol']} "
                f"({worst_pair.get('netPnl')} net PnL)."
            )

    if timeframe_outcomes:
        sorted_tf = [
            row
            for row in timeframe_outcomes
            if row.get("key") != "NOT_SET" and row.get("label") != "Not set"
        ]
        best_tf = sorted(
            sorted_tf,
            key=lambda row: _as_number(row.get("netPnl")) or 0,
            reverse=True,
        )[0] if sorted_tf else None
        worst_tf = sorted(
            sorted_tf,
            key=lambda row: _as_number(row.get("netPnl")) or 0,
        )[0] if sorted_tf else None

        if best_tf:
            strengths.append(
                f"Best chart timeframe: {best_tf.get('label')} ({best_tf.get('wins')}W/"
                f"{best_tf.get('losses')}L, {best_tf.get('netPnl')} net PnL)."
            )

        if worst_tf and (_as_number(worst_tf.get("netPnl")) or 0) < 0:
            weaknesses.append(
                f"Weakest chart timeframe: {worst_tf.get('label')} ({worst_tf.get('wins')}W/"
                f"{worst_tf.get('losses')}L, {worst_tf.get('netPnl')} net PnL)."
            )

    direction_rows = _pick_metric_groups(direction)
    if len(direction_rows) >= 2:
        long_row = next(
            (row for row in direction_rows if "long" in _row_label(row).lower()),
            None,
        )
        short_row = next(
            (row for row in direction_rows if "short" in _row_label(row).lower()),
            None,
        )

        if long_row and short_row:
            patterns.append(
                f"Long {long_row.get('netPnl')} net PnL vs Short {short_row.get('netPnl')} net PnL — "
                "compare whether direction matches your bias and plan."
            )

    period_a = period_comparison.get("periodA")
    period_b = period_comparison.get("periodB")

    if _is_record(period_a) and _is_record(period_b):
        patterns.append(
            f"Latest {_read_numeric_field(period_a, 'tradeCount') or 0} trades: "
            f"{_read_string_field(period_a, 'netPnl')} net PnL vs previous "
            f"{_read_numeric_field(period_b, 'tradeCount') or 0}: "
            f"{_read_string_field(period_b, 'netPnl')}."
        )

        delta_win_rate = _read_numeric_field(period_comparison.get("deltas"), "winRate")
        if delta_win_rate is not None and delta_win_rate < -5:
            weaknesses.append(
                f"Win rate dropped {abs(delta_win_rate):.1f} pts in your latest 20 trades "
                "vs the prior 20."
            )
        elif delta_win_rate is not None and delta_win_rate > 5:
            strengths.append(
                f"Win rate improved {delta_win_rate:.1f} pts in your latest 20 trades vs the prior 20."
            )

    after_losses = behavior.get("afterLossesComparison")
    after_loss_trade_count = _read_numeric_field(after_losses, "tradeCount")

    if after_loss_trade_count is not None and after_loss_trade_count > 0:
        patterns.append(
            f"After {_read_numeric_field(after_losses, 'lossStreakThreshold') or 2}+ losses: "
            f"{after_loss_trade_count} trades, {_read_string_field(after_losses, 'netPnl')} net PnL, "
            f"{_read_string_field(after_losses, 'winRate')}% win rate."
        )

        baseline_win_rate = _read_numeric_field(after_losses, "baselineWinRate")
        after_win_rate = _read_numeric_field(after_losses, "winRate")

        if (
            baseline_win_rate is not None
            and after_win_rate is not None
            and after_win_rate < baseline_win_rate - 5
        ):
            weaknesses.append(
                "Performance deteriorates after loss streaks — likely revenge or size-up behavior."
            )
            rules_for_next_trades.append(
                "After 2 consecutive losses, stop for 30 minutes or reduce size to baseline risk."
            )

    longest_losing_streak = summary.get("longestLosingStreak")
    if longest_losing_streak is not None and longest_losing_streak >= 3:
        patterns.append(
            f"Longest losing streak: {longest_losing_streak} trades — "
            "review journal entries from that stretch."
        )

    if money_expectancy is not None and money_expectancy > 0:
        recommendations.append(
            f"Positive money expectancy ({money_expectancy:.2f} {currency}/trade) — scale slowly "
            "only on A+ setups that match your best instrument/session."
        )

    max_drawdown = _as_number(summary.get("maxDrawdownPercentage"))
    if max_drawdown is not None and max_drawdown > 10:
        weaknesses.append(
            f"Max drawdown reached {max_drawdown:.1f}% — risk per trade may be too high."
        )
        rules_for_next_trades.append(
            "Hard daily stop: halt trading if daily drawdown exceeds your pre-set limit."
        )

    if journal_coverage:
        gaps = [
            gap
            for gap in (
                _coverage_gap(
                    "Chart timeframe",
                    journal_coverage.get("withChartTimeframe"),
                    journal_coverage.get("closedTrades"),
                    "Log the chart TF on every trade to unlock timeframe win/loss analysis.",
                ),
                _coverage_gap(
                    "Pre-trade plan",
                    journal_coverage.get("withPreTradePlan"),
                    journal_coverage.get("closedTrades"),
                    "Write your plan before entry so plan compliance can be measured.",
                ),
                _coverage_gap(
                    "Post-trade review",
                    journal_coverage.get("withPostTradePlan"),
                    journal_coverage.get("closedTrades"),
                    "Capture what went well/wrong after each close.",
                ),
                _coverage_gap(
                    "Entry criteria tags",
                    journal_coverage.get("withEntryCriteria"),
                    journal_coverage.get("closedTrades"),
                    "Tag entry criteria on every trade to find your real edge.",
                ),
                _coverage_gap(
                    "Mistake tags",
                    journal_coverage.get("withMistakesTagged"),
                    journal_coverage.get("closedTrades"),
                    "Tag mistakes on losers to stop repeating the same errors.",
                ),
            )
            if gap
        ]
        data_limitations.extend(gaps)

    if sample_size < 5:
        data_limitations.append(
            f"Only {sample_size} closed trades — insights are preliminary until you reach at least 20."
        )
    elif sample_size < 20:
        data_limitations.append(
            f"{sample_size} closed trades — patterns are directionally useful but not yet statistically strong."
        )

    if not strategies:
        data_limitations.append(
            "No strategy tags found — assign strategies to trades so coaching can compare setups."
        )

    if not tags:
        data_limitations.append(
            "No entry criteria tags found — tag setups to identify which criteria actually work."
        )

    if not mistakes and (summary.get("lossCount") or 0) > 0:
        data_limitations.append(
            "No mistakes tagged on losing trades — tag errors to target loss reduction."
        )

    if provider_label:
        data_limitations.append(
            f"Generated in analytics-only mode ({provider_label} unavailable). "
            "Connect OpenAI for deeper narrative coaching on the same data."
        )

    if net_pnl is not None:
        summary_text = (
            f"Based on {sample_size} closed trades: net PnL "
            f"{'+' if net_pnl >= 0 else ''}{net_pnl:.2f} {currency}"
            + (f", win rate {win_rate}" if win_rate else "")
            + (f", profit factor {profit_factor:.2f}" if profit_factor is not None else "")
            + (f", {r_expectancy:.2f}R expectancy" if r_expectancy is not None else "")
            + "."
            + (" Your data shows clear strengths to lean into." if strengths else "")
            + (
                " There are specific leaks to address before increasing size."
                if weaknesses
                else ""
            )
        ).strip()
    else:
        summary_text = f"Analysis based on {sample_size} closed trades."

    return AiStructuredOutput(
        summary=summary_text,
        strengths=strengths[:6],
        weaknesses=weaknesses[:6],
        patterns=patterns[:6],
        recommendations=(
            recommendations[:8]
            if recommendations
            else [
                "Double down on instruments and sessions with positive net PnL and win rate above your average.",
                "Review losing trades for repeated mistakes and untagged entry criteria.",
            ]
        ),
        rules_for_next_trades=(
            rules_for_next_trades[:6]
            if rules_for_next_trades
            else [
                "Trade only tagged setups that match your best-performing entry criteria.",
                "Stop for the day after hitting your max loss or max consecutive losses.",
            ]
        ),
        data_limitations=data_limitations[:6],
    )
