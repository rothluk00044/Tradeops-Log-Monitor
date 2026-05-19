"""Anomaly detection for order event streams."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from .models import (
    Anomaly,
    AnomalySeverity,
    AnomalyType,
    EventType,
    OrderEvent,
    OrderLifecycle,
    OrderStatus,
    ParseResult,
)


SINGLETON_LIFECYCLE_EVENTS = {
    EventType.ORDER_NEW,
    EventType.ORDER_ACK,
    EventType.ORDER_REJECT,
    EventType.ORDER_CANCEL,
}


def detect_anomalies(
    parse_result: ParseResult,
    lifecycles: Iterable[OrderLifecycle],
    *,
    slow_ack_ms: int = 500,
    reject_spike_threshold: int = 3,
    symbol_activity_threshold: int = 10,
) -> list[Anomaly]:
    orders = list(lifecycles)
    anomalies: list[Anomaly] = []

    anomalies.extend(_parse_issue_anomalies(parse_result))
    anomalies.extend(_unknown_event_anomalies(parse_result.events))

    for lifecycle in orders:
        anomalies.extend(_lifecycle_anomalies(lifecycle, slow_ack_ms=slow_ack_ms))

    anomalies.extend(_reject_spike_anomalies(orders, threshold=reject_spike_threshold))
    anomalies.extend(_symbol_activity_anomalies(orders, threshold=symbol_activity_threshold))
    return anomalies


def has_critical_anomalies(anomalies: Iterable[Anomaly]) -> bool:
    return any(anomaly.severity is AnomalySeverity.CRITICAL for anomaly in anomalies)


def _parse_issue_anomalies(parse_result: ParseResult) -> list[Anomaly]:
    return [
        Anomaly(
            anomaly_type=AnomalyType.PARSE_ISSUE,
            severity=issue.severity,
            message=issue.message,
            line_number=issue.line_number,
            details={"raw_line": issue.raw_line},
        )
        for issue in parse_result.issues
    ]


def _unknown_event_anomalies(events: Iterable[OrderEvent]) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    for event in events:
        if event.event_type is EventType.UNKNOWN:
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.UNKNOWN_EVENT_TYPE,
                    severity=AnomalySeverity.WARNING,
                    message=f"Unknown event type {event.raw_event_type}.",
                    order_id=event.order_id,
                    symbol=event.symbol,
                    line_number=event.line_number,
                    details={"raw_event_type": event.raw_event_type},
                )
            )
    return anomalies


def _lifecycle_anomalies(lifecycle: OrderLifecycle, *, slow_ack_ms: int) -> list[Anomaly]:
    anomalies: list[Anomaly] = []

    if lifecycle.ack_latency_ms is not None and lifecycle.ack_latency_ms > slow_ack_ms:
        anomalies.append(
            Anomaly(
                anomaly_type=AnomalyType.SLOW_ACK,
                severity=AnomalySeverity.WARNING,
                message=f"ACK latency {lifecycle.ack_latency_ms:.1f}ms exceeded {slow_ack_ms}ms.",
                order_id=lifecycle.order_id,
                symbol=lifecycle.symbol,
                details={"ack_latency_ms": lifecycle.ack_latency_ms, "threshold_ms": slow_ack_ms},
            )
        )

    if _is_missing_ack(lifecycle):
        anomalies.append(
            Anomaly(
                anomaly_type=AnomalyType.MISSING_ACK,
                severity=AnomalySeverity.WARNING,
                message="Order has a NEW event but no ACK event.",
                order_id=lifecycle.order_id,
                symbol=lifecycle.symbol,
            )
        )

    if _has_fill_before_ack(lifecycle):
        anomalies.append(
            Anomaly(
                anomaly_type=AnomalyType.FILL_BEFORE_ACK,
                severity=AnomalySeverity.CRITICAL,
                message="Order has a fill before its ACK event.",
                order_id=lifecycle.order_id,
                symbol=lifecycle.symbol,
                details={
                    "first_fill_time": lifecycle.first_fill_time.isoformat() if lifecycle.first_fill_time else None,
                    "ack_time": lifecycle.ack_time.isoformat() if lifecycle.ack_time else None,
                },
            )
        )

    anomalies.extend(_duplicate_lifecycle_event_anomalies(lifecycle))
    return anomalies


def _is_missing_ack(lifecycle: OrderLifecycle) -> bool:
    if lifecycle.new_time is None or lifecycle.ack_time is not None:
        return False
    return lifecycle.status not in {OrderStatus.REJECTED}


def _has_fill_before_ack(lifecycle: OrderLifecycle) -> bool:
    if lifecycle.first_fill_time is None:
        return False
    if lifecycle.ack_time is None:
        return True
    return lifecycle.first_fill_time < lifecycle.ack_time


def _duplicate_lifecycle_event_anomalies(lifecycle: OrderLifecycle) -> list[Anomaly]:
    counts = Counter(event.event_type for event in lifecycle.events)
    anomalies: list[Anomaly] = []
    for event_type in SINGLETON_LIFECYCLE_EVENTS:
        if counts[event_type] > 1:
            anomalies.append(
                Anomaly(
                    anomaly_type=AnomalyType.DUPLICATE_LIFECYCLE_EVENT,
                    severity=AnomalySeverity.WARNING,
                    message=f"Order has duplicate {event_type.value} events.",
                    order_id=lifecycle.order_id,
                    symbol=lifecycle.symbol,
                    details={"event_type": event_type.value, "count": counts[event_type]},
                )
            )
    return anomalies


def _reject_spike_anomalies(orders: list[OrderLifecycle], *, threshold: int) -> list[Anomaly]:
    counts = Counter(
        lifecycle.reject_reason or "UNKNOWN"
        for lifecycle in orders
        if lifecycle.status is OrderStatus.REJECTED
    )
    return [
        Anomaly(
            anomaly_type=AnomalyType.REJECT_SPIKE,
            severity=AnomalySeverity.WARNING,
            message=f"Reject reason {reason} occurred {count} times.",
            details={"reason": reason, "count": count, "threshold": threshold},
        )
        for reason, count in sorted(counts.items())
        if count >= threshold
    ]


def _symbol_activity_anomalies(orders: list[OrderLifecycle], *, threshold: int) -> list[Anomaly]:
    counts = Counter(lifecycle.symbol or "UNKNOWN" for lifecycle in orders)
    return [
        Anomaly(
            anomaly_type=AnomalyType.SYMBOL_ACTIVITY_SPIKE,
            severity=AnomalySeverity.INFO,
            message=f"Symbol {symbol} appeared on {count} orders.",
            symbol=symbol,
            details={"symbol": symbol, "count": count, "threshold": threshold},
        )
        for symbol, count in sorted(counts.items())
        if count >= threshold
    ]
