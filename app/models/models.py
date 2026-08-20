from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import (
    AccountSource,
    AccountType,
    AssetClass,
    ChartTimeframe,
    ExecutionType,
    MarketBias,
    MT5ConnectionStatus,
    Mt5SyncEventType,
    PlanComplianceStatus,
    ScreenshotType,
    TradeDirection,
    TradeEmotion,
    TradeEventType,
    TradeSource,
    TradeStatus,
    pg_enum,
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    clerk_user_id: Mapped[str] = mapped_column(String, unique=True)
    email: Mapped[str] = mapped_column(String)
    timezone: Mapped[str] = mapped_column(String, default="UTC", server_default="UTC")
    preferred_currency: Mapped[str] = mapped_column(
        String, default="USD", server_default="USD"
    )
    selected_trading_account_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("trading_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    selected_trading_account: Mapped[TradingAccount | None] = relationship(
        "TradingAccount",
        foreign_keys=[selected_trading_account_id],
        back_populates="selected_by_users",
    )
    trading_accounts: Mapped[list[TradingAccount]] = relationship(
        "TradingAccount",
        back_populates="user",
        foreign_keys="TradingAccount.user_id",
        cascade="all, delete-orphan",
    )
    trades: Mapped[list[Trade]] = relationship(back_populates="user", cascade="all, delete-orphan")
    strategies: Mapped[list[Strategy]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    tags: Mapped[list[Tag]] = relationship(back_populates="user", cascade="all, delete-orphan")
    mistakes: Mapped[list[Mistake]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    daily_journals: Mapped[list[DailyJournal]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    mt5_connections: Mapped[list[MT5Connection]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    ai_analyses: Mapped[list[AiAnalysis]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    ai_chat_messages: Mapped[list[AiChatMessage]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class TradingAccount(Base):
    __tablename__ = "trading_accounts"
    __table_args__ = (Index("ix_trading_accounts_user_id_is_active", "user_id", "is_active"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String)
    type: Mapped[AccountType] = mapped_column(pg_enum(AccountType))
    source: Mapped[AccountSource] = mapped_column(
        pg_enum(AccountSource),
        default=AccountSource.MANUAL,
        server_default=AccountSource.MANUAL.value,
    )
    broker_name: Mapped[str | None] = mapped_column(String, nullable=True)
    currency: Mapped[str] = mapped_column(String, default="USD", server_default="USD")
    starting_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    current_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(
        "User", back_populates="trading_accounts", foreign_keys=[user_id]
    )
    selected_by_users: Mapped[list[User]] = relationship(
        "User",
        back_populates="selected_trading_account",
        foreign_keys="User.selected_trading_account_id",
    )
    risk_settings: Mapped[RiskSettings | None] = relationship(
        back_populates="trading_account", cascade="all, delete-orphan", uselist=False
    )
    instrument_specs: Mapped[list[InstrumentSpec]] = relationship(
        back_populates="trading_account", cascade="all, delete-orphan"
    )
    trades: Mapped[list[Trade]] = relationship(
        back_populates="trading_account", cascade="all, delete-orphan"
    )
    daily_journals: Mapped[list[DailyJournal]] = relationship(
        back_populates="trading_account", cascade="all, delete-orphan"
    )
    mt5_connection: Mapped[MT5Connection | None] = relationship(
        back_populates="trading_account", cascade="all, delete-orphan", uselist=False
    )


class InstrumentSpec(Base):
    __tablename__ = "instrument_specs"
    __table_args__ = (
        UniqueConstraint("trading_account_id", "symbol"),
        Index("ix_instrument_specs_trading_account_id", "trading_account_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    trading_account_id: Mapped[str] = mapped_column(
        String, ForeignKey("trading_accounts.id", ondelete="CASCADE")
    )
    symbol: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    asset_class: Mapped[AssetClass] = mapped_column(pg_enum(AssetClass))
    digits: Mapped[int] = mapped_column(Integer)
    point: Mapped[Decimal] = mapped_column(Numeric(18, 10))
    tick_size: Mapped[Decimal] = mapped_column(Numeric(18, 10))
    tick_value_profit: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    tick_value_loss: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    contract_size: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    volume_min: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    volume_max: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    volume_step: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    base_currency: Mapped[str | None] = mapped_column(String, nullable=True)
    profit_currency: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    trading_account: Mapped[TradingAccount] = relationship(
        back_populates="instrument_specs"
    )


class RiskSettings(Base):
    __tablename__ = "risk_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    trading_account_id: Mapped[str] = mapped_column(
        String, ForeignKey("trading_accounts.id", ondelete="CASCADE"), unique=True
    )
    default_risk_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("1"), server_default="1"
    )
    max_risk_per_trade_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("2"), server_default="2"
    )
    max_daily_risk_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("5"), server_default="5"
    )
    max_daily_loss_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("5"), server_default="5"
    )
    max_open_risk_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("10"), server_default="10"
    )
    max_trades_per_day: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    max_consecutive_losses: Mapped[int] = mapped_column(
        Integer, default=3, server_default="3"
    )
    strict_mode: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    trading_account: Mapped[TradingAccount] = relationship(back_populates="risk_settings")


class Strategy(Base):
    __tablename__ = "strategies"
    __table_args__ = (
        UniqueConstraint("user_id", "name"),
        Index("ix_strategies_user_id_is_active", "user_id", "is_active"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="strategies")
    trade_strategies: Mapped[list[TradeStrategy]] = relationship(
        back_populates="strategy", cascade="all, delete-orphan"
    )


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="tags")
    trade_tags: Mapped[list[TradeTag]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )


class Mistake(Base):
    __tablename__ = "mistakes"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="mistakes")
    trade_mistakes: Mapped[list[TradeMistake]] = relationship(
        back_populates="mistake", cascade="all, delete-orphan"
    )


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trades_user_id_status", "user_id", "status"),
        Index("ix_trades_trading_account_id_opened_at", "trading_account_id", "opened_at"),
        Index("ix_trades_symbol", "symbol"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))
    trading_account_id: Mapped[str] = mapped_column(
        String, ForeignKey("trading_accounts.id", ondelete="CASCADE")
    )
    source: Mapped[TradeSource] = mapped_column(
        pg_enum(TradeSource),
        default=TradeSource.MANUAL,
        server_default=TradeSource.MANUAL.value,
    )
    external_position_id: Mapped[str | None] = mapped_column(String, nullable=True)
    symbol: Mapped[str] = mapped_column(String)
    chart_timeframe: Mapped[ChartTimeframe | None] = mapped_column(
        pg_enum(ChartTimeframe), nullable=True
    )
    asset_class: Mapped[AssetClass] = mapped_column(pg_enum(AssetClass))
    direction: Mapped[TradeDirection] = mapped_column(pg_enum(TradeDirection))
    status: Mapped[TradeStatus] = mapped_column(
        pg_enum(TradeStatus),
        default=TradeStatus.OPEN,
        server_default=TradeStatus.OPEN.value,
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    average_entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 10))
    average_exit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 10), nullable=True)
    initial_volume: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    current_volume: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    initial_stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 10), nullable=True)
    current_stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 10), nullable=True)
    initial_take_profit: Mapped[Decimal | None] = mapped_column(Numeric(18, 10), nullable=True)
    current_take_profit: Mapped[Decimal | None] = mapped_column(Numeric(18, 10), nullable=True)
    account_balance_at_entry: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    initial_risk_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    initial_risk_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    planned_rr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    gross_pnl: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0"
    )
    commission: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0"
    )
    swap: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0"
    )
    fees: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0"
    )
    net_pnl: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0"
    )
    realized_r: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    mfe_money: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    mae_money: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    mfe_r: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    mae_r: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    max_favorable_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 10), nullable=True
    )
    max_adverse_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="trades")
    trading_account: Mapped[TradingAccount] = relationship(back_populates="trades")
    executions: Mapped[list[TradeExecution]] = relationship(
        back_populates="trade", cascade="all, delete-orphan"
    )
    events: Mapped[list[TradeEvent]] = relationship(
        back_populates="trade", cascade="all, delete-orphan"
    )
    review: Mapped[TradeReview | None] = relationship(
        back_populates="trade", cascade="all, delete-orphan", uselist=False
    )
    trade_tags: Mapped[list[TradeTag]] = relationship(
        back_populates="trade", cascade="all, delete-orphan"
    )
    trade_mistakes: Mapped[list[TradeMistake]] = relationship(
        back_populates="trade", cascade="all, delete-orphan"
    )
    trade_strategies: Mapped[list[TradeStrategy]] = relationship(
        back_populates="trade", cascade="all, delete-orphan"
    )
    screenshots: Mapped[list[TradeScreenshot]] = relationship(
        back_populates="trade", cascade="all, delete-orphan"
    )


class TradeExecution(Base):
    __tablename__ = "trade_executions"
    __table_args__ = (Index("ix_trade_executions_trade_id_executed_at", "trade_id", "executed_at"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    trade_id: Mapped[str] = mapped_column(String, ForeignKey("trades.id", ondelete="CASCADE"))
    external_deal_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    type: Mapped[ExecutionType] = mapped_column(pg_enum(ExecutionType))
    price: Mapped[Decimal] = mapped_column(Numeric(18, 10))
    volume: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    profit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0"
    )
    commission: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0"
    )
    swap: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0"
    )
    fee: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0"
    )
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    trade: Mapped[Trade] = relationship(back_populates="executions")


class TradeEvent(Base):
    __tablename__ = "trade_events"
    __table_args__ = (Index("ix_trade_events_trade_id_occurred_at", "trade_id", "occurred_at"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    trade_id: Mapped[str] = mapped_column(String, ForeignKey("trades.id", ondelete="CASCADE"))
    type: Mapped[TradeEventType] = mapped_column(pg_enum(TradeEventType))
    previous_value: Mapped[str | None] = mapped_column(String, nullable=True)
    new_value: Mapped[str | None] = mapped_column(String, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)

    trade: Mapped[Trade] = relationship(back_populates="events")


class TradeReview(Base):
    __tablename__ = "trade_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    trade_id: Mapped[str] = mapped_column(
        String, ForeignKey("trades.id", ondelete="CASCADE"), unique=True
    )
    market_bias: Mapped[MarketBias | None] = mapped_column(pg_enum(MarketBias), nullable=True)
    pre_trade_plan: Mapped[str | None] = mapped_column(String, nullable=True)
    post_trade_plan: Mapped[str | None] = mapped_column(String, nullable=True)
    pre_trade_emotion: Mapped[TradeEmotion | None] = mapped_column(
        pg_enum(TradeEmotion), nullable=True
    )
    post_trade_emotion: Mapped[TradeEmotion | None] = mapped_column(
        pg_enum(TradeEmotion), nullable=True
    )
    confidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plan_compliance: Mapped[PlanComplianceStatus | None] = mapped_column(
        pg_enum(PlanComplianceStatus), nullable=True
    )
    entry_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    what_went_well: Mapped[str | None] = mapped_column(String, nullable=True)
    what_went_wrong: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    lesson: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    trade: Mapped[Trade] = relationship(back_populates="review")


class TradeTag(Base):
    __tablename__ = "trade_tags"

    trade_id: Mapped[str] = mapped_column(
        String, ForeignKey("trades.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        String, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    trade: Mapped[Trade] = relationship(back_populates="trade_tags")
    tag: Mapped[Tag] = relationship(back_populates="trade_tags")


class TradeMistake(Base):
    __tablename__ = "trade_mistakes"

    trade_id: Mapped[str] = mapped_column(
        String, ForeignKey("trades.id", ondelete="CASCADE"), primary_key=True
    )
    mistake_id: Mapped[str] = mapped_column(
        String, ForeignKey("mistakes.id", ondelete="CASCADE"), primary_key=True
    )

    trade: Mapped[Trade] = relationship(back_populates="trade_mistakes")
    mistake: Mapped[Mistake] = relationship(back_populates="trade_mistakes")


class TradeStrategy(Base):
    __tablename__ = "trade_strategies"

    trade_id: Mapped[str] = mapped_column(
        String, ForeignKey("trades.id", ondelete="CASCADE"), primary_key=True
    )
    strategy_id: Mapped[str] = mapped_column(
        String, ForeignKey("strategies.id", ondelete="CASCADE"), primary_key=True
    )

    trade: Mapped[Trade] = relationship(back_populates="trade_strategies")
    strategy: Mapped[Strategy] = relationship(back_populates="trade_strategies")


class TradeScreenshot(Base):
    __tablename__ = "trade_screenshots"
    __table_args__ = (
        Index("ix_trade_screenshots_trade_id_created_at", "trade_id", "created_at"),
        Index("ix_trade_screenshots_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    trade_id: Mapped[str] = mapped_column(String, ForeignKey("trades.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String)
    type: Mapped[ScreenshotType] = mapped_column(pg_enum(ScreenshotType))
    url: Mapped[str] = mapped_column(String)
    file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    trade: Mapped[Trade] = relationship(back_populates="screenshots")


class DailyJournal(Base):
    __tablename__ = "daily_journals"
    __table_args__ = (
        UniqueConstraint("user_id", "trading_account_id", "date"),
        Index("ix_daily_journals_user_id_date", "user_id", "date"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))
    trading_account_id: Mapped[str] = mapped_column(
        String, ForeignKey("trading_accounts.id", ondelete="CASCADE")
    )
    date: Mapped[date] = mapped_column(Date)
    confidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market_bias: Mapped[MarketBias | None] = mapped_column(pg_enum(MarketBias), nullable=True)
    pre_trade_plan: Mapped[str | None] = mapped_column(String, nullable=True)
    post_trade_plan: Mapped[str | None] = mapped_column(String, nullable=True)
    what_went_well: Mapped[str | None] = mapped_column(String, nullable=True)
    what_went_wrong: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="daily_journals")
    trading_account: Mapped[TradingAccount] = relationship(back_populates="daily_journals")


class MT5Connection(Base):
    __tablename__ = "mt5_connections"
    __table_args__ = (
        UniqueConstraint("mt5_login", "server_name"),
        Index("ix_mt5_connections_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))
    trading_account_id: Mapped[str] = mapped_column(
        String, ForeignKey("trading_accounts.id", ondelete="CASCADE"), unique=True
    )
    mt5_login: Mapped[str | None] = mapped_column(String, nullable=True)
    server_name: Mapped[str | None] = mapped_column(String, nullable=True)
    broker_name: Mapped[str | None] = mapped_column(String, nullable=True)
    connection_key_hash: Mapped[str] = mapped_column(String)
    status: Mapped[MT5ConnectionStatus] = mapped_column(
        pg_enum(MT5ConnectionStatus),
        default=MT5ConnectionStatus.DISCONNECTED,
        server_default=MT5ConnectionStatus.DISCONNECTED.value,
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_position_snapshot_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ea_version: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="mt5_connections")
    trading_account: Mapped[TradingAccount] = relationship(back_populates="mt5_connection")
    processed_deals: Mapped[list[Mt5ProcessedDeal]] = relationship(
        back_populates="mt5_connection", cascade="all, delete-orphan"
    )
    position_snapshots: Mapped[list[Mt5PositionSnapshot]] = relationship(
        back_populates="mt5_connection", cascade="all, delete-orphan"
    )
    sync_events: Mapped[list[Mt5SyncEvent]] = relationship(
        back_populates="mt5_connection", cascade="all, delete-orphan"
    )


class Mt5ProcessedDeal(Base):
    __tablename__ = "mt5_processed_deals"
    __table_args__ = (UniqueConstraint("mt5_connection_id", "external_deal_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    mt5_connection_id: Mapped[str] = mapped_column(
        String, ForeignKey("mt5_connections.id", ondelete="CASCADE")
    )
    external_deal_id: Mapped[str] = mapped_column(String)
    trade_id: Mapped[str | None] = mapped_column(String, nullable=True)
    execution_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    mt5_connection: Mapped[MT5Connection] = relationship(back_populates="processed_deals")


class Mt5PositionSnapshot(Base):
    __tablename__ = "mt5_position_snapshots"
    __table_args__ = (
        UniqueConstraint("mt5_connection_id", "external_position_id"),
        Index("ix_mt5_position_snapshots_mt5_connection_id_snapshot_at", "mt5_connection_id", "snapshot_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    mt5_connection_id: Mapped[str] = mapped_column(
        String, ForeignKey("mt5_connections.id", ondelete="CASCADE")
    )
    external_position_id: Mapped[str] = mapped_column(String)
    trade_id: Mapped[str | None] = mapped_column(String, nullable=True)
    symbol: Mapped[str] = mapped_column(String)
    direction: Mapped[TradeDirection] = mapped_column(pg_enum(TradeDirection))
    volume: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    open_price: Mapped[Decimal] = mapped_column(Numeric(18, 10))
    current_price: Mapped[Decimal] = mapped_column(Numeric(18, 10))
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 10), nullable=True)
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(18, 10), nullable=True)
    floating_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    swap: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0"
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    mt5_connection: Mapped[MT5Connection] = relationship(back_populates="position_snapshots")


class Mt5SyncEvent(Base):
    __tablename__ = "mt5_sync_events"
    __table_args__ = (
        UniqueConstraint("mt5_connection_id", "external_event_id"),
        Index("ix_mt5_sync_events_mt5_connection_id_occurred_at", "mt5_connection_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    mt5_connection_id: Mapped[str] = mapped_column(
        String, ForeignKey("mt5_connections.id", ondelete="CASCADE")
    )
    external_event_id: Mapped[str | None] = mapped_column(String, nullable=True)
    event_type: Mapped[Mt5SyncEventType] = mapped_column(pg_enum(Mt5SyncEventType))
    external_position_id: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    mt5_connection: Mapped[MT5Connection] = relationship(back_populates="sync_events")


class AiAnalysis(Base):
    __tablename__ = "ai_analyses"
    __table_args__ = (Index("ix_ai_analyses_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))
    trading_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
    sample_size: Mapped[int] = mapped_column(Integer)
    sample_confidence: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(String)
    strengths: Mapped[Any] = mapped_column(JSON)
    weaknesses: Mapped[Any] = mapped_column(JSON)
    patterns: Mapped[Any] = mapped_column(JSON)
    recommendations: Mapped[Any] = mapped_column(JSON)
    rules_for_next_trades: Mapped[Any] = mapped_column(JSON)
    data_limitations: Mapped[Any] = mapped_column(JSON)
    context: Mapped[Any] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="ai_analyses")


class AiChatMessage(Base):
    __tablename__ = "ai_chat_messages"
    __table_args__ = (Index("ix_ai_chat_messages_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))
    question: Mapped[str] = mapped_column(String)
    answer: Mapped[Any] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="ai_chat_messages")
