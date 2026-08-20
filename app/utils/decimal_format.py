from decimal import Decimal


def format_decimal(value: Decimal | int | float | str | None) -> str | None:
    """Serialize a numeric decimal without trailing zeros."""
    if value is None:
        return None

    normalized = format(Decimal(str(value)), "f")

    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")

    return normalized
