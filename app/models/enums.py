from enum import Enum

from sqlalchemy import Enum as SAEnum


def pg_enum(enum_class: type[Enum]) -> SAEnum:
    return SAEnum(
        enum_class,
        name=enum_class.__name__,
        create_type=False,
        native_enum=True,
    )


class MT5ConnectionStatus(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


class Mt5SyncEventType(str, Enum):
    TRADE_OPEN = "TRADE_OPEN"
    TRADE_CLOSE = "TRADE_CLOSE"
    PARTIAL_CLOSE = "PARTIAL_CLOSE"
    SL_CHANGED = "SL_CHANGED"
    TP_CHANGED = "TP_CHANGED"
    VOLUME_CHANGED = "VOLUME_CHANGED"
    POSITION_SNAPSHOT = "POSITION_SNAPSHOT"
    RECONCILE = "RECONCILE"
    HEARTBEAT = "HEARTBEAT"


class AccountType(str, Enum):
    PERSONAL = "PERSONAL"
    DEMO = "DEMO"
    PROP_CHALLENGE = "PROP_CHALLENGE"
    FUNDED = "FUNDED"
    OTHER = "OTHER"


class AccountSource(str, Enum):
    MANUAL = "MANUAL"
    MT5 = "MT5"


class AssetClass(str, Enum):
    FOREX = "FOREX"
    COMMODITY = "COMMODITY"
    INDEX = "INDEX"
    CRYPTO = "CRYPTO"
    STOCK = "STOCK"
    OTHER = "OTHER"


class ChartTimeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"


class TradeSource(str, Enum):
    MANUAL = "MANUAL"
    MT5 = "MT5"
    CSV = "CSV"


class TradeDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class TradeStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class ExecutionType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"


class TradeEventType(str, Enum):
    OPENED = "OPENED"
    SL_CHANGED = "SL_CHANGED"
    TP_CHANGED = "TP_CHANGED"
    VOLUME_CHANGED = "VOLUME_CHANGED"
    PARTIAL_CLOSE = "PARTIAL_CLOSE"
    BREAKEVEN = "BREAKEVEN"
    CLOSED = "CLOSED"


class TradeEmotion(str, Enum):
    CALM = "CALM"
    CONFIDENT = "CONFIDENT"
    FEAR = "FEAR"
    FOMO = "FOMO"
    GREED = "GREED"
    IMPATIENT = "IMPATIENT"
    REVENGE = "REVENGE"
    OTHER = "OTHER"


class MarketBias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class PlanComplianceStatus(str, Enum):
    FOLLOWED = "FOLLOWED"
    PARTIALLY_FOLLOWED = "PARTIALLY_FOLLOWED"
    DID_NOT_FOLLOW = "DID_NOT_FOLLOW"
    NOT_REVIEWED = "NOT_REVIEWED"


class ScreenshotType(str, Enum):
    BEFORE_TRADE = "BEFORE_TRADE"
    DURING_TRADE = "DURING_TRADE"
    AFTER_TRADE = "AFTER_TRADE"
