from datetime import datetime
from typing import TypedDict
from zoneinfo import ZoneInfo

MONTH_ABBR = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]

WEEKDAY_TO_INDEX: dict[str, int] = {
    "Mon": 0,
    "Tue": 1,
    "Wed": 2,
    "Thu": 3,
    "Fri": 4,
    "Sat": 5,
    "Sun": 6,
}

DAY_OF_WEEK_LABELS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


class ZonedDateParts(TypedDict):
    hour: int
    day_of_week: int
    month_key: str
    month_label: str


def get_zoned_date_parts(date: datetime, time_zone: str) -> ZonedDateParts:
    local = date.astimezone(ZoneInfo(time_zone))
    hour = local.hour
    weekday = local.strftime("%a")
    year = local.strftime("%Y")
    month = MONTH_ABBR[local.month - 1]

    return {
        "hour": 0 if hour == 24 else hour,
        "day_of_week": WEEKDAY_TO_INDEX.get(weekday, 0),
        "month_key": f"{year}-{month}",
        "month_label": f"{month} {year}",
    }


def format_hour_label(hour: int) -> str:
    normalized = hour % 24
    suffix = "PM" if normalized >= 12 else "AM"
    hour12 = 12 if normalized % 12 == 0 else normalized % 12
    return f"{hour12}:00 {suffix}"
