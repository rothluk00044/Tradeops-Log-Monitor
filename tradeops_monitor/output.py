"""Formatting helpers for text and JSON command output."""

from __future__ import annotations

import json
from typing import Iterable

from .models import AnalysisReport, Anomaly, MetricsSummary, OrderLifecycle


def format_report(report: AnalysisReport, *, output_format: str = "text", show_orders: bool = False) -> str:
    if output_format == "text":
        return format_text_report(report, show_orders=show_orders)
    if output_format == "json":
        return format_json_report(report, show_orders=show_orders)
    raise ValueError(f"Unsupported output format: {output_format}")


def format_json_report(report: AnalysisReport, *, show_orders: bool = False) -> str:
    return json.dumps(report.to_dict(include_orders=show_orders), indent=2, sort_keys=True)


def format_text_report(report: AnalysisReport, *, show_orders: bool = False) -> str:
    lines = [
        "TradeOps Log Monitor Summary",
        "=" * 28,
        f"Source: {report.source_file}",
        f"Input format: {report.input_format}",
        f"Parsed events: {len(report.parse_result.events)}",
        f"Parse issues: {len(report.parse_result.issues)}",
        "",
    ]
    lines.extend(_format_metrics(report.metrics))
    lines.extend(_format_anomalies(report.anomalies))

    if show_orders:
        lines.extend(_format_orders(report.lifecycles.values()))

    return "\n".join(lines).rstrip() + "\n"


def _format_metrics(metrics: MetricsSummary) -> list[str]:
    lines = [
        "Metrics",
        "- Total orders: " + str(metrics.total_orders),
        "- Filled: " + str(metrics.filled_count),
        "- Rejected: " + str(metrics.rejected_count),
        "- Canceled: " + str(metrics.canceled_count),
        "- Open/incomplete: " + str(metrics.open_incomplete_count),
        "- Slow ACKs: " + str(metrics.slow_ack_count),
        "- Avg ACK latency: " + _format_ms(metrics.average_ack_latency_ms),
        "- Min ACK latency: " + _format_ms(metrics.min_ack_latency_ms),
        "- Max ACK latency: " + _format_ms(metrics.max_ack_latency_ms),
    ]
    lines.append("- Reject reasons: " + _format_counter(metrics.reject_reasons))
    lines.append("- Counts by symbol: " + _format_counter(metrics.counts_by_symbol))
    lines.append("- Counts by side: " + _format_counter(metrics.counts_by_side))
    lines.append("")
    return lines


def _format_anomalies(anomalies: list[Anomaly]) -> list[str]:
    lines = ["Anomalies"]
    if not anomalies:
        return lines + ["- None", ""]

    for anomaly in anomalies:
        location = []
        if anomaly.order_id:
            location.append(f"order={anomaly.order_id}")
        if anomaly.symbol:
            location.append(f"symbol={anomaly.symbol}")
        if anomaly.line_number:
            location.append(f"line={anomaly.line_number}")
        location_text = f" ({', '.join(location)})" if location else ""
        lines.append(f"- [{anomaly.severity.value}] {anomaly.anomaly_type.value}: {anomaly.message}{location_text}")
    lines.append("")
    return lines


def _format_orders(lifecycles: Iterable[OrderLifecycle]) -> list[str]:
    orders = sorted(lifecycles, key=lambda order: order.order_id)
    lines = ["Orders"]
    if not orders:
        return lines + ["- None", ""]

    for order in orders:
        latency = _format_ms(order.ack_latency_ms)
        lines.append(
            "- "
            f"{order.order_id}: status={order.status.value}, "
            f"symbol={order.symbol or 'UNKNOWN'}, side={order.side or 'UNKNOWN'}, "
            f"filled={order.filled_qty}/{order.ordered_qty if order.ordered_qty is not None else 'UNKNOWN'}, "
            f"ack_latency={latency}"
        )
    lines.append("")
    return lines


def _format_ms(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}ms"


def _format_counter(counter: dict[str, int]) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counter.items()))
