"""Core dataclasses and enums used across parsing, analysis, and output."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    ORDER_NEW = "ORDER_NEW"
    ORDER_ACK = "ORDER_ACK"
    ORDER_FILL = "ORDER_FILL"
    ORDER_REJECT = "ORDER_REJECT"
    ORDER_CANCEL = "ORDER_CANCEL"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_raw(cls, raw_value: str) -> "EventType":
        try:
            return cls(raw_value)
        except ValueError:
            return cls.UNKNOWN


class OrderStatus(StrEnum):
    NEW_ONLY = "NEW_ONLY"
    ACKED = "ACKED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"
    UNKNOWN = "UNKNOWN"
    INCOMPLETE = "INCOMPLETE"


class AnomalySeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class OrderEvent:
    timestamp: datetime | None
    event_type: EventType
    raw_event_type: str
    order_id: str | None
    symbol: str | None = None
    side: str | None = None
    qty: int | None = None
    price: float | None = None
    reason: str | None = None
    fields: dict[str, str] = field(default_factory=dict)
    line_number: int | None = None
    raw_line: str = ""
    source_format: str = "plain"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "event_type": self.event_type.value,
            "raw_event_type": self.raw_event_type,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "qty": self.qty,
            "price": self.price,
            "reason": self.reason,
            "fields": dict(self.fields),
            "line_number": self.line_number,
            "source_format": self.source_format,
        }


@dataclass(frozen=True)
class ParseIssue:
    line_number: int
    message: str
    raw_line: str
    severity: AnomalySeverity = AnomalySeverity.WARNING

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_number": self.line_number,
            "message": self.message,
            "raw_line": self.raw_line,
            "severity": self.severity.value,
        }


@dataclass(frozen=True)
class ParseResult:
    events: list[OrderEvent] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)

    @property
    def malformed_count(self) -> int:
        return len(self.issues)
