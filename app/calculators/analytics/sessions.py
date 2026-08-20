from typing import Literal, TypedDict

TradingSession = Literal["ASIA", "LONDON", "OVERLAP", "NEW_YORK", "OFF_HOURS"]

TRADING_SESSION_LABELS: dict[TradingSession, str] = {
    "ASIA": "Asia",
    "LONDON": "London",
    "OVERLAP": "London / New York overlap",
    "NEW_YORK": "New York",
    "OFF_HOURS": "Off hours",
}


def get_trading_session(local_hour: int) -> TradingSession:
    if 0 <= local_hour <= 7:
        return "ASIA"

    if 8 <= local_hour <= 12:
        return "LONDON"

    if 13 <= local_hour <= 16:
        return "OVERLAP"

    if 17 <= local_hour <= 20:
        return "NEW_YORK"

    return "OFF_HOURS"


def _format_hour12(hour: int) -> str:
    normalized = hour % 24
    suffix = "PM" if normalized >= 12 else "AM"
    hour12 = 12 if normalized % 12 == 0 else normalized % 12
    return f"{hour12}:00 {suffix}"


def format_two_hour_window_label(start_hour: int) -> str:
    end_hour = (start_hour + 2) % 24
    return f"{_format_hour12(start_hour)} – {_format_hour12(end_hour)}"


def get_two_hour_window_start(local_hour: int) -> int:
    return (local_hour // 2) * 2
