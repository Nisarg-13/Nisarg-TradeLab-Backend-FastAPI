from __future__ import annotations

import json
from typing import Any

STRING_ARRAY_FIELDS = (
    "strengths",
    "weaknesses",
    "patterns",
    "recommendations",
    "rulesForNextTrades",
    "dataLimitations",
)


def _format_evidence_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [
            item.strip()
            for item in value
            if isinstance(item, str) and item.strip()
        ]

    if isinstance(value, str) and value.strip():
        return [value.strip()]

    return []


def _to_bullet_string(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()

    if value is None:
        return ""

    if isinstance(value, dict):
        record = value

        if isinstance(record.get("title"), str) and isinstance(record.get("observation"), str):
            parts = [f"{record['title']}: {record['observation']}"]
            evidence = _format_evidence_list(record.get("evidence"))

            if evidence:
                parts.append(f"Evidence: {'; '.join(evidence)}")

            if isinstance(record.get("interpretation"), str):
                parts.append(record["interpretation"])

            if isinstance(record.get("confidence"), str):
                parts.append(f"Confidence: {record['confidence']}")

            if isinstance(record.get("estimatedImpact"), str):
                parts.append(f"Impact: {record['estimatedImpact']}")

            if isinstance(record.get("status"), str):
                parts.append(f"Status: {record['status']}")

            return " ".join(parts)

        if isinstance(record.get("action"), str):
            prefix = f"{record['priority']}. " if isinstance(record.get("priority"), (int, float)) else ""
            parts = [f"{prefix}{record['action']}"]

            if isinstance(record.get("reason"), str):
                parts.append(f"Reason: {record['reason']}")

            if isinstance(record.get("successMetric"), str):
                parts.append(f"Success metric: {record['successMetric']}")

            return " ".join(parts)

        if isinstance(record.get("rule"), str):
            parts = [record["rule"]]

            if isinstance(record.get("addresses"), str):
                parts.append(f"Addresses: {record['addresses']}")

            if isinstance(record.get("evidence"), str):
                parts.append(f"Evidence: {record['evidence']}")

            return " ".join(parts)

        if isinstance(record.get("issue"), str):
            parts = [record["issue"]]

            if isinstance(record.get("impact"), str):
                parts.append(f"Impact: {record['impact']}")

            if isinstance(record.get("action"), str):
                parts.append(f"Action: {record['action']}")

            return " ".join(parts)

        text = (
            record.get("text")
            or record.get("point")
            or record.get("message")
            or record.get("description")
            or record.get("title")
        )

        if isinstance(text, str):
            return text.strip()

        return json.dumps(value)

    if isinstance(value, (int, float, bool)):
        return str(value)

    return ""


def _normalize_summary(value: Any) -> str:
    if isinstance(value, str):
        return value

    if value is None:
        return ""

    if isinstance(value, dict):
        record = value

        if isinstance(record.get("performance"), str):
            parts = [record["performance"]]

            if isinstance(record.get("biggestStrength"), str):
                parts.append(f"Biggest strength: {record['biggestStrength']}")

            if isinstance(record.get("biggestRisk"), str):
                parts.append(f"Biggest risk: {record['biggestRisk']}")

            if isinstance(record.get("priority"), str):
                parts.append(f"Priority: {record['priority']}")

            return "\n\n".join(parts)

        return json.dumps(value)

    if isinstance(value, (int, float, bool)):
        return str(value)

    return ""


def normalize_structured_output(raw: Any) -> Any:
    if not isinstance(raw, dict):
        return raw

    normalized: dict[str, Any] = dict(raw)

    if not isinstance(normalized.get("summary"), str):
        normalized["summary"] = _normalize_summary(normalized.get("summary"))

    for field in STRING_ARRAY_FIELDS:
        value = normalized.get(field)

        if isinstance(value, list):
            normalized[field] = [
                item for item in (_to_bullet_string(item) for item in value) if item
            ]
            continue

        if isinstance(value, str) and value.strip():
            normalized[field] = [value.strip()]
            continue

        normalized[field] = []

    return normalized


def normalize_chat_answer(raw: Any) -> Any:
    if not isinstance(raw, dict):
        return raw

    normalized: dict[str, Any] = dict(raw)

    if not isinstance(normalized.get("summary"), str):
        normalized["summary"] = _normalize_summary(normalized.get("summary"))

    for field in ("evidence", "limitations"):
        value = normalized.get(field)

        if isinstance(value, list):
            normalized[field] = [
                item for item in (_to_bullet_string(item) for item in value) if item
            ]
            continue

        normalized[field] = []

    return normalized
