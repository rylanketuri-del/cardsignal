"""Configurable thresholds for Card Intelligence V1 — Sprint 8.7."""

from __future__ import annotations

CARD_INTELLIGENCE_ALGORITHM_VERSION = "CARD_INTELLIGENCE_V1"

MIN_MARKET_SAMPLE_SIZE = 2
MEANINGFUL_BID_LISTINGS = 1
MEANINGFUL_TOTAL_BIDS = 2

# Component score weights for card_signal_score (renormalized when inputs missing)
SIGNAL_WEIGHTS = {
    "market_activity": 0.20,
    "demand": 0.25,
    "momentum": 0.25,
    "scarcity": 0.20,
}

# Recommendation thresholds
BUY_MIN_SIGNAL_SCORE = 65.0
SELL_MAX_SIGNAL_SCORE = 42.0
BUY_MIN_DEMAND_SCORE = 50.0
BUY_STRONG_DEMAND_SCORE = 58.0
BUY_MIN_MOMENTUM_SCORE = 52.0
BUY_STRONG_MOMENTUM_SCORE = 55.0
BUY_MIN_MARKET_ACTIVITY = 50.0
SCARCITY_ALONE_CAP = 70.0
SCARCITY_ALONE_DEMAND_MAX = 45.0

HOLD_MIN_SIGNAL_SCORE = 43.0
HOLD_MAX_SIGNAL_SCORE = 64.0

# Conviction thresholds
CONVICTION_HIGH_MIN_SCORE = 75.0
CONVICTION_HIGH_MAX_SCORE = 25.0
CONVICTION_MEDIUM_MIN_EVIDENCE = 2

QUALITY_RANK = {
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "INSUFFICIENT": 0,
}

INSUFFICIENT_EVIDENCE_MESSAGE = (
    "More market history is needed before CardSignal can issue a full card recommendation."
)

DISCLAIMER = (
    "CardSignal provides market intelligence, not financial advice. "
    "Active listing data may differ from confirmed sale prices."
)
