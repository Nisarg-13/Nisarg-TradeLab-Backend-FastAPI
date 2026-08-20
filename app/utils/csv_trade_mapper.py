from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.utils.csv_parse import ParsedCsv, normalize_header, row_to_record


@dataclass(slots=True)
class MappedCsvTrade:
    row_number: int
    external_position_id: str | None
    symbol: str
    direction: Literal["LONG", "SHORT"]
    opened_at: datetime
    closed_at: datetime
    entry_price: float
    exit_price: float
    volume: float
    stop_loss: float | None
    take_profit: float | None
    commission: float
    swap: float
    net_pnl: float


@dataclass(slots=True)
class CsvRowError:
    row_number: int
    message: str


def _parse_direction(value: str) -> Literal["LONG", "SHORT"] | None:
    normalized = value.strip().lower()

    if normalized in {"buy", "long", "0"}:
        return "LONG"

    if normalized in {"sell", "short", "1"}:
        return "SHORT"

    return None


def _parse_number(value: str | None) -> float | None:
    if not value:
        return None

    cleaned = value.replace(" ", "").replace(",", "")
    try:
        parsed = float(cleaned)
    except ValueError:
        return None

    return parsed if parsed == parsed else None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    return parsed


def _detect_format(headers: list[str]) -> Literal["MT5", "GENERIC"]:
    normalized = [normalize_header(header) for header in headers]

    if (
        "position" in normalized
        and "profit" in normalized
        and "symbol" in normalized
    ):
        return "MT5"

    return "GENERIC"


def _get_value(record: dict[str, str], aliases: list[str]) -> str | None:
    for alias in aliases:
        if record.get(alias):
            return record[alias]

    return None


def _map_mt5_row(
    row_number: int, record: dict[str, str]
) -> tuple[MappedCsvTrade | None, CsvRowError | None]:
    symbol = (_get_value(record, ["symbol"]) or "").upper()
    direction = _parse_direction(_get_value(record, ["type"]) or "")
    volume = _parse_number(_get_value(record, ["volume"]))
    entry_price = _parse_number(_get_value(record, ["price"]))
    exit_price = _parse_number(
        _get_value(record, ["price_1", "price2", "close_price", "exit_price"])
    )
    opened_at = _parse_date(_get_value(record, ["time"]))
    closed_at = _parse_date(
        _get_value(record, ["time_1", "time1", "close_time", "closed_at"])
    )
    net_pnl = _parse_number(_get_value(record, ["profit", "net_pnl"]))
    commission = _parse_number(_get_value(record, ["commission"])) or 0
    swap = _parse_number(_get_value(record, ["swap"])) or 0

    if not symbol or not direction or volume is None or entry_price is None:
        return None, CsvRowError(
            row_number=row_number,
            message="Missing required MT5 fields (symbol, type, volume, price).",
        )

    if not opened_at or not closed_at or exit_price is None or net_pnl is None:
        return None, CsvRowError(
            row_number=row_number,
            message="Missing MT5 close fields (close time, close price, profit).",
        )

    return (
        MappedCsvTrade(
            row_number=row_number,
            external_position_id=_get_value(record, ["position"]),
            symbol=symbol,
            direction=direction,
            opened_at=opened_at,
            closed_at=closed_at,
            entry_price=entry_price,
            exit_price=exit_price,
            volume=volume,
            stop_loss=_parse_number(_get_value(record, ["s_l", "sl", "stop_loss"])),
            take_profit=_parse_number(
                _get_value(record, ["t_p", "tp", "take_profit"])
            ),
            commission=commission,
            swap=swap,
            net_pnl=net_pnl,
        ),
        None,
    )


def _map_generic_row(
    row_number: int, record: dict[str, str]
) -> tuple[MappedCsvTrade | None, CsvRowError | None]:
    symbol = (
        _get_value(record, ["symbol", "pair", "instrument"]) or ""
    ).upper()
    direction = _parse_direction(
        _get_value(record, ["direction", "side", "type"]) or ""
    )
    volume = _parse_number(_get_value(record, ["volume", "lots", "size"]))
    entry_price = _parse_number(
        _get_value(record, ["entry_price", "open_price", "price_open"])
    )
    exit_price = _parse_number(
        _get_value(record, ["exit_price", "close_price", "price_close"])
    )
    opened_at = _parse_date(
        _get_value(record, ["opened_at", "open_time", "entry_time"])
    )
    closed_at = _parse_date(
        _get_value(record, ["closed_at", "close_time", "exit_time"])
    )
    net_pnl = _parse_number(
        _get_value(record, ["net_pnl", "profit", "pnl", "result"])
    )
    commission = _parse_number(_get_value(record, ["commission"])) or 0
    swap = _parse_number(_get_value(record, ["swap"])) or 0

    if (
        not symbol
        or not direction
        or volume is None
        or entry_price is None
        or exit_price is None
        or not opened_at
        or not closed_at
        or net_pnl is None
    ):
        return None, CsvRowError(
            row_number=row_number,
            message=(
                "Missing required generic CSV fields (symbol, direction, volume, "
                "prices, times, net pnl)."
            ),
        )

    return (
        MappedCsvTrade(
            row_number=row_number,
            external_position_id=_get_value(
                record, ["external_position_id", "position_id", "ticket"]
            ),
            symbol=symbol,
            direction=direction,
            opened_at=opened_at,
            closed_at=closed_at,
            entry_price=entry_price,
            exit_price=exit_price,
            volume=volume,
            stop_loss=_parse_number(_get_value(record, ["stop_loss", "sl"])),
            take_profit=_parse_number(_get_value(record, ["take_profit", "tp"])),
            commission=commission,
            swap=swap,
            net_pnl=net_pnl,
        ),
        None,
    )


def map_csv_trades(
    parsed: ParsedCsv,
    format: Literal["AUTO", "MT5", "GENERIC"] = "AUTO",
) -> dict[str, object]:
    resolved_format = _detect_format(parsed.headers) if format == "AUTO" else format

    trades: list[MappedCsvTrade] = []
    errors: list[CsvRowError] = []

    for index, row in enumerate(parsed.rows):
        record = row_to_record(parsed.headers, row)
        row_number = index + 2
        mapped = (
            _map_mt5_row(row_number, record)
            if resolved_format == "MT5"
            else _map_generic_row(row_number, record)
        )
        trade, error = mapped

        if error:
            errors.append(error)
            continue

        if trade:
            trades.append(trade)

    return {
        "format": resolved_format,
        "trades": trades,
        "errors": errors,
    }


def build_duplicate_key(trade: MappedCsvTrade) -> str:
    if trade.external_position_id:
        return f"position:{trade.external_position_id}"

    return (
        f"hash:{trade.symbol}:{trade.opened_at.isoformat()}:"
        f"{trade.closed_at.isoformat()}:{trade.volume}:{trade.entry_price}"
    )


def escape_csv_value(value: str | float | int | None) -> str:
    if value is None:
        return ""

    string_value = str(value)

    if any(char in string_value for char in '",\n'):
        return f'"{string_value.replace(chr(34), chr(34) + chr(34))}"'

    return string_value


def to_csv(headers: list[str], rows: list[list[str | float | int | None]]) -> str:
    lines = [
        ",".join(escape_csv_value(header) for header in headers),
        *[
            ",".join(escape_csv_value(cell) for cell in row)
            for row in rows
        ],
    ]

    return "\n".join(lines)
