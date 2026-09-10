"""Strict public contracts for the Mochatrade advisory risk gate."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class IntentKind(StrEnum):
    OPEN = "OPEN"
    INCREASE = "INCREASE"
    REDUCE = "REDUCE"
    CLOSE = "CLOSE"


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class Session(StrEnum):
    PRE = "PRE"
    REGULAR = "REGULAR"
    POST = "POST"
    OVERNIGHT = "OVERNIGHT"
    CLOSED = "CLOSED"
    EXCHANGE_HALT = "EXCHANGE_HALT"
    CORPORATE_ACTION = "CORPORATE_ACTION"


class OrderIntent(StrictModel):
    kind: IntentKind
    side: Side
    notional_usd: Decimal = Field(gt=0, le=Decimal("100000000"), max_digits=16, decimal_places=2)
    requested_leverage: Decimal = Field(gt=0, le=Decimal("100"), max_digits=6, decimal_places=2)


class PortfolioPosition(StrictModel):
    symbol: str = Field(min_length=1, max_length=12, pattern=r"^[A-Za-z][A-Za-z0-9.\-]*$")
    notional_usd: Decimal = Field(gt=0, le=Decimal("1000000000"), max_digits=18, decimal_places=2)
    side: Side = Side.BUY
    sector: str | None = Field(default=None, max_length=48)
    correlation_group: str | None = Field(default=None, max_length=48)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper()


class AccountExposure(StrictModel):
    equity_usd: Decimal = Field(gt=0, le=Decimal("1000000000"), max_digits=18, decimal_places=2)
    margin_available_usd: Decimal = Field(ge=0, le=Decimal("1000000000"), max_digits=18, decimal_places=2)
    position_notional_usd: Decimal = Field(ge=0, le=Decimal("1000000000"), max_digits=18, decimal_places=2)
    liquidation_price: Decimal | None = Field(default=None, gt=0, le=Decimal("10000000"), max_digits=16, decimal_places=6)
    current_leverage: Decimal | None = Field(default=None, ge=0, le=Decimal("100"), max_digits=6, decimal_places=2)
    position_side: Side | None = None
    portfolio_positions: list[PortfolioPosition] = Field(default_factory=list, max_length=100)


class VenueMarketContext(StrictModel):
    mark_price: Decimal = Field(gt=0, le=Decimal("10000000"), max_digits=16, decimal_places=6)
    oracle_price: Decimal | None = Field(default=None, gt=0, le=Decimal("10000000"), max_digits=16, decimal_places=6)
    mid_price: Decimal | None = Field(default=None, gt=0, le=Decimal("10000000"), max_digits=16, decimal_places=6)
    best_bid: Decimal | None = Field(default=None, gt=0, le=Decimal("10000000"), max_digits=16, decimal_places=6)
    best_ask: Decimal | None = Field(default=None, gt=0, le=Decimal("10000000"), max_digits=16, decimal_places=6)
    open_interest: Decimal | None = Field(default=None, ge=0, le=Decimal("1000000000000"))
    funding: Decimal | None = Field(default=None, ge=Decimal("-1"), le=Decimal("1"))
    volume: Decimal | None = Field(default=None, ge=0, le=Decimal("1000000000000"))
    event_time: datetime
    session: Session | None = None

    @field_validator("event_time")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("event_time must include a timezone")
        return value

    @model_validator(mode="after")
    def valid_book(self):
        if self.best_bid is not None and self.best_ask is not None and self.best_bid > self.best_ask:
            raise ValueError("best_bid cannot exceed best_ask")
        return self


class RiskCheckRequest(StrictModel):
    request_id: str = Field(min_length=6, max_length=96, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]+$")
    symbol: str = Field(min_length=1, max_length=12, pattern=r"^[A-Za-z][A-Za-z0-9.\-]*$")
    intent: OrderIntent
    account: AccountExposure
    market: VenueMarketContext
    demo_scenario: str | None = Field(default=None, pattern=r"^(NORMAL|POISONED_MARK|RECOVERY)$")

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def intent_matches_exposure(self):
        if self.intent.kind in {IntentKind.REDUCE, IntentKind.CLOSE} and self.account.position_notional_usd <= 0:
            raise ValueError("REDUCE/CLOSE requires an existing position")
        return self


class ReplayRequest(StrictModel):
    passport_id: str = Field(pattern=r"^mbp_[0-9a-f]{24}$")
    policy_version: str = Field(
        default="CURRENT",
        pattern=r"^(ORIGINAL|CURRENT|WITHOUT_SAFETY_GATE|mocha-risk-v1\.(?:0\.0|1\.0))$",
    )


class OutcomeRequest(StrictModel):
    outcome: str = Field(pattern=r"^(accepted|rejected|reduced|closed|expired|manually_reviewed)$")
