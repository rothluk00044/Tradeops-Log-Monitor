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


@dataclass(frozen=True)
class OrderLifecycle:
    order_id: str
    events: list[OrderEvent]
    status: OrderStatus
    symbol: str | None = None
    side: str | None = None
    ordered_qty: int | None = None
    filled_qty: int = 0
    new_time: datetime | None = None
    ack_time: datetime | None = None
    first_fill_time: datetime | None = None
    final_time: datetime | None = None
    ack_latency_ms: float | None = None
    reject_reason: str | None = None
    cancel_reason: str | None = None

    def to_dict(self, include_events: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "order_id": self.order_id,
            "status": self.status.value,
            "symbol": self.symbol,
            "side": self.side,
            "ordered_qty": self.ordered_qty,
            "filled_qty": self.filled_qty,
            "new_time": self.new_time.isoformat() if self.new_time else None,
            "ack_time": self.ack_time.isoformat() if self.ack_time else None,
            "first_fill_time": self.first_fill_time.isoformat() if self.first_fill_time else None,
            "final_time": self.final_time.isoformat() if self.final_time else None,
            "ack_latency_ms": self.ack_latency_ms,
            "reject_reason": self.reject_reason,
            "cancel_reason": self.cancel_reason,
        }
        if include_events:
            payload["events"] = [event.to_dict() for event in self.events]
        return payload


@dataclass(frozen=True)
class MetricsSummary:
    total_orders: int
    filled_count: int
    rejected_count: int
    canceled_count: int
    open_incomplete_count: int
    average_ack_latency_ms: float | None
    min_ack_latency_ms: float | None
    max_ack_latency_ms: float | None
    slow_ack_count: int
    reject_reasons: dict[str, int]
    counts_by_symbol: dict[str, int]
    counts_by_side: dict[str, int]
    status_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_orders": self.total_orders,
            "filled_count": self.filled_count,
            "rejected_count": self.rejected_count,
            "canceled_count": self.canceled_count,
            "open_incomplete_count": self.open_incomplete_count,
            "average_ack_latency_ms": self.average_ack_latency_ms,
            "min_ack_latency_ms": self.min_ack_latency_ms,
            "max_ack_latency_ms": self.max_ack_latency_ms,
            "slow_ack_count": self.slow_ack_count,
            "reject_reasons": dict(self.reject_reasons),
            "counts_by_symbol": dict(self.counts_by_symbol),
            "counts_by_side": dict(self.counts_by_side),
            "status_counts": dict(self.status_counts),
        }
