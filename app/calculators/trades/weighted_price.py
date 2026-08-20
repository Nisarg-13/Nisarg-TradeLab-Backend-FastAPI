from typing import TypedDict


class VolumePriceRow(TypedDict):
    price: float
    volume: float


class VolumeOnlyRow(TypedDict):
    volume: float


def calculate_weighted_average_price(rows: list[VolumePriceRow]) -> float:
    if len(rows) == 0:
        return 0

    total_volume = sum(row["volume"] for row in rows)

    if total_volume <= 0:
        return 0

    weighted_sum = sum(row["price"] * row["volume"] for row in rows)

    return weighted_sum / total_volume


def sum_volume(rows: list[VolumeOnlyRow]) -> float:
    return sum(row["volume"] for row in rows)
