"""Unified signal schema for multi-source data ingestion."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from agentcy.brand.core.config import utc_now


class SignalSource(StrEnum):
    """Known signal sources."""

    NEWS = "news"
    SOCIAL_TWITTER = "social_twitter"
    SOCIAL_REDDIT = "social_reddit"
    SOCIAL_LINKEDIN = "social_linkedin"
    FINANCIAL_STOCK = "financial_stock"
    FINANCIAL_CURRENCY = "financial_currency"
    SEC_FILING = "sec_filing"
    PATENT = "patent"
    COMPETITOR = "competitor"
    INTERNAL = "internal"
    CUSTOM = "custom"


class SignalType(StrEnum):
    """Types of signals."""

    NEWS = "news"
    MENTION = "mention"
    SENTIMENT_SHIFT = "sentiment_shift"
    PRICE_MOVEMENT = "price_movement"
    FILING = "filing"
    PRODUCT_LAUNCH = "product_launch"
    COMPETITOR_MOVE = "competitor_move"
    TREND = "trend"
    ANOMALY = "anomaly"
    ALERT = "alert"


class Urgency(StrEnum):
    """Signal urgency levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Signal(BaseModel):
    """Unified signal model for all data sources.

    All external data should be normalized to this schema before
    entering the processing pipeline.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    source: SignalSource
    signal_type: SignalType
    brand: str
    timestamp: datetime = Field(default_factory=utc_now)

    # Content
    title: str
    content: str
    url: str | None = None

    # Scoring
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    sentiment: float | None = Field(default=None, ge=-1.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    urgency: Urgency = Urgency.MEDIUM

    # Context
    entities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Provenance
    raw_data: dict[str, Any] | None = Field(default=None, exclude=True)


class SignalBatch(BaseModel):
    """A batch of signals from a single fetch operation."""

    source: SignalSource
    brand: str
    fetched_at: datetime = Field(default_factory=utc_now)
    signals: list[Signal] = Field(default_factory=list)
    cursor: str | None = None  # For pagination
    has_more: bool = False


class SignalFilter(BaseModel):
    """Filter criteria for querying signals."""

    brand: str | None = None
    sources: list[SignalSource] | None = None
    signal_types: list[SignalType] | None = None
    urgency_min: Urgency | None = None
    relevance_min: float | None = None
    since: datetime | None = None
    until: datetime | None = None
    tags: list[str] | None = None
    limit: int = 100

    def matches(self, signal: Signal) -> bool:
        """Check if a signal matches this filter."""
        if self.brand and signal.brand != self.brand:
            return False
        if self.sources and signal.source not in self.sources:
            return False
        if self.signal_types and signal.signal_type not in self.signal_types:
            return False
        if self.relevance_min and signal.relevance_score < self.relevance_min:
            return False
        if self.since and signal.timestamp < self.since:
            return False
        if self.until and signal.timestamp > self.until:
            return False
        if self.tags and not any(t in signal.tags for t in self.tags):
            return False
        return True
