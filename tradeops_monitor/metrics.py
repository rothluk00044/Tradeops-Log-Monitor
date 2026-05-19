"""Metric calculations for reconstructed order lifecycles."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from .models import MetricsSummary, OrderLifecycle, OrderStatus


OPEN_OR_INCOMPLETE_STATUSES = {
    OrderStatus.NEW_ONLY,
    OrderStatus.ACKED,
    OrderStatus.PARTIALLY_FILLED,
    OrderStatus.INCOMPLETE,
    OrderStatus.UNKNOWN,
}


def calculate_metrics(
    lifecycles: Iterable[OrderLifecycle],
    *,
    slow_ack_ms: int = 500,
) -> MetricsSummary:
    orders = list(lifecycles)
    ack_latencies = [
        lifecycle.ack_latency_ms
        for lifecycle in orders
        if lifecycle.ack_latency_ms is not None
    ]

    return MetricsSummary(
        total_orders=len(orders),
        filled_count=_count_status(orders, OrderStatus.FILLED),
        rejected_count=_count_status(orders, OrderStatus.REJECTED),
        canceled_count=_count_status(orders, OrderStatus.CANCELED),
        open_incomplete_count=sum(1 for order in orders if order.status in OPEN_OR_INCOMPLETE_STATUSES),
        average_ack_latency_ms=_average(ack_latencies),
        min_ack_latency_ms=min(ack_latencies) if ack_latencies else None,
        max_ack_latency_ms=max(ack_latencies) if ack_latencies else None,
        slow_ack_count=sum(1 for latency in ack_latencies if latency > slow_ack_ms),
        reject_reasons=_counter_dict(
            lifecycle.reject_reason or "UNKNOWN"
            for lifecycle in orders
            if lifecycle.status is OrderStatus.REJECTED
        ),
        counts_by_symbol=_counter_dict(lifecycle.symbol or "UNKNOWN" for lifecycle in orders),
        counts_by_side=_counter_dict(lifecycle.side or "UNKNOWN" for lifecycle in orders),
        status_counts=_counter_dict(lifecycle.status.value for lifecycle in orders),
    )


def _count_status(orders: list[OrderLifecycle], status: OrderStatus) -> int:
    return sum(1 for order in orders if order.status is status)


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _counter_dict(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))
