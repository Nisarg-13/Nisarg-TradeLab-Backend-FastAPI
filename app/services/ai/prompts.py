from __future__ import annotations

from typing import Any

AI_COACH_SYSTEM_PROMPT = """You are an expert trading performance coach for Nisarg's TradeLab.

Your job is to help the trader maximize profits, minimize losses, and improve process quality using ONLY the supplied metrics.

Rules:
- Never invent statistics. Cite specific numbers, symbols, sessions, strategies, tags, or timeframes from context.
- Never recalculate canonical statistics — use values exactly as provided.
- Always respect sample size and sampleConfidence. Be tentative when data is limited.
- Do not claim causation without evidence. Do not guarantee profitability.
- Do not generate trade signals or tell the trader what to buy/sell now.
- Focus on historical execution, risk discipline, journal quality, timing, instruments, and measurable patterns.

Respond with valid JSON only."""


def build_analysis_prompt(context: dict[str, Any]) -> str:
    import json

    return f"""
Analyze this trader's TradeLab performance data.

All canonical statistics in the context have already been calculated by
TradeLab and are authoritative.

Your objective is to identify:

1. STRONGEST REPEATABLE BEHAVIOR
Where historical risk-adjusted performance appears strongest.

2. BIGGEST PERFORMANCE LEAKS
Where losses, negative expectancy, excessive drawdown, mistakes, poor
execution, or poor plan compliance concentrate.

3. PROCESS QUALITY
Whether following the trading plan, maintaining risk discipline, and avoiding
mistakes are associated with better outcomes.

4. RISK BEHAVIOR
Pay particular attention to:
- risk after losses
- risk after winning streaks
- drawdown
- oversized trades
- consecutive-loss behavior

5. EXECUTION QUALITY
When available, evaluate:
- planned R versus realized R
- exit reasons
- SL modifications
- MFE / MAE
- exit efficiency
- holding time

6. EDGE QUALITY
When Edge Finder data exists, identify promising and weak combinations,
but discount low-confidence or very small samples.

7. PROFIT / LOSS CONCENTRATION
Determine whether performance is broadly repeatable or dependent on a small
number of unusually large winning or losing trades.

8. IMPROVEMENT EXPERIMENT
Recommend a small number of measurable process changes for the next 20 trades.

9. DATA QUALITY
Use journalCoverage and missing-data information to identify what the trader
should record more consistently.

PRIORITIZATION

Prioritize insights using approximately this hierarchy:

1. Large negative expectancy / large loss leakage
2. Risk-discipline problems
3. Plan-compliance problems
4. Strong repeatable expectancy
5. Execution problems
6. Timing / session patterns
7. Instrument / direction patterns
8. Journal data gaps

Do not overemphasize small differences.

If two groups perform similarly, say that no meaningful distinction is
currently supported.

Do not recommend trading more frequently merely because a category has
positive PnL.

OUTPUT

Return exactly this JSON structure:

{{
  "summary": {{
    "performance": "2-3 sentence description of current performance using supplied metrics.",
    "biggestStrength": "Single most important supported positive finding.",
    "biggestRisk": "Single most important supported weakness or risk.",
    "priority": "The single highest-priority improvement."
  }},

  "strengths": [
    {{
      "title": "Short descriptive title",
      "observation": "What the data shows.",
      "evidence": [
        "Exact supplied metric or comparison",
        "Exact supplied metric or comparison"
      ],
      "sampleSize": null,
      "confidence": "INSUFFICIENT | VERY_LOW | LOW | MODERATE | HIGHER | UNKNOWN",
      "interpretation": "Conservative interpretation of the evidence."
    }}
  ],

  "weaknesses": [
    {{
      "title": "Short descriptive title",
      "observation": "What the data shows.",
      "evidence": [
        "Exact supplied metric or comparison"
      ],
      "sampleSize": null,
      "confidence": "INSUFFICIENT | VERY_LOW | LOW | MODERATE | HIGHER | UNKNOWN",
      "estimatedImpact": "HIGH | MEDIUM | LOW | UNKNOWN",
      "interpretation": "Why this deserves attention."
    }}
  ],

  "patterns": [
    {{
      "title": "Pattern name",
      "observation": "Observed historical pattern.",
      "evidence": [
        "Supporting supplied metric"
      ],
      "confidence": "INSUFFICIENT | VERY_LOW | LOW | MODERATE | HIGHER | UNKNOWN",
      "status": "PROMISING | NEGATIVE | NEUTRAL | NEEDS_MORE_DATA"
    }}
  ],

  "recommendations": [
    {{
      "priority": 1,
      "action": "Specific process change.",
      "reason": "Evidence-based reason.",
      "successMetric": "Metric TradeLab should evaluate after more trades.",
      "reviewAfterTrades": 20
    }}
  ],

  "rulesForNextTrades": [
    {{
      "rule": "Concrete trading-process rule.",
      "addresses": "The specific historical weakness it is intended to address.",
      "evidence": "Relevant supplied evidence."
    }}
  ],

  "experiments": [
    {{
      "hypothesis": "What the trader wants to test.",
      "change": "One controlled process change.",
      "keepConstant": "What should remain unchanged.",
      "measurement": "How TradeLab will evaluate the experiment.",
      "minimumTrades": 20
    }}
  ],

  "dataLimitations": [
    {{
      "issue": "Missing or insufficient information.",
      "impact": "What analysis cannot currently be trusted or performed.",
      "action": "What should be recorded going forward."
    }}
  ]
}}

IMPORTANT:

- Usually return 3-5 high-value insights rather than filling arrays with weak observations.
- Quality is more important than quantity.
- Do not repeat the same finding across strengths, patterns, and recommendations.
- If evidence is insufficient, say so.
- Do not invent missing sampleSize values.
- Use null when the context does not provide a required numeric value.

Context:

{json.dumps(context, indent=2)}
"""
