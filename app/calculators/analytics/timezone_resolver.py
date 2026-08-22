from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def resolve_analytics_timezone(
    user_timezone: str | None,
    query_timezone: str | None = None,
) -> str:
    for candidate in (query_timezone, user_timezone, "UTC"):
        if not candidate:
            continue

        try:
            ZoneInfo(candidate)
        except ZoneInfoNotFoundError:
            continue

        return candidate

    return "UTC"
