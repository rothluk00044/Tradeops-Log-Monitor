"""Dashboard and export helpers built from analysis reports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

from .models import AnalysisReport, AnomalySeverity, AnomalyType, OrderLifecycle, OrderStatus


@dataclass(frozen=True)
class SeverityAssessment:
    level: str
    score: int
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"level": self.level, "score": self.score, "reasons": list(self.reasons)}


ANOMALY_EXPLANATIONS = {
    AnomalyType.PARSE_ISSUE.value: "The parser found malformed or incomplete input that should be reviewed.",
    AnomalyType.UNKNOWN_EVENT_TYPE.value: "An event type was not recognized by the current parser rules.",
    AnomalyType.SLOW_ACK.value: "An order ACK took longer than the configured latency threshold.",
    AnomalyType.MISSING_ACK.value: "An order has a NEW event but no ACK event in the analyzed stream.",
    AnomalyType.FILL_BEFORE_ACK.value: "A fill appears before the order was acknowledged, which is a sequencing issue.",
    AnomalyType.DUPLICATE_LIFECYCLE_EVENT.value: "A lifecycle event that is expected once appeared multiple times.",
    AnomalyType.REJECT_SPIKE.value: "A reject reason crossed the configured spike threshold.",
    AnomalyType.SYMBOL_ACTIVITY_SPIKE.value: "A symbol crossed the configured activity threshold.",
}


def assess_operational_severity(report: AnalysisReport) -> SeverityAssessment:
    metrics = report.metrics
    total_orders = max(metrics.total_orders, 1)
    reject_rate = metrics.rejected_count / total_orders
    malformed_count = report.parse_result.malformed_count
    critical_count = sum(1 for anomaly in report.anomalies if anomaly.severity is AnomalySeverity.CRITICAL)
    missing_ack_count = count_anomalies(report, AnomalyType.MISSING_ACK)
    fill_before_ack_count = count_anomalies(report, AnomalyType.FILL_BEFORE_ACK)

    score = 0
    reasons: list[str] = []

    if critical_count:
        score += 40
        reasons.append(f"{critical_count} critical anomalies")
    if reject_rate >= 0.10 and metrics.rejected_count >= 3:
        score += 25
        reasons.append(f"{metrics.rejected_count} rejected orders ({reject_rate:.1%})")
    if metrics.slow_ack_count >= 5 or metrics.slow_ack_count / total_orders >= 0.10:
        score += 20
        reasons.append(f"{metrics.slow_ack_count} slow ACKs")
    if missing_ack_count >= 3:
        score += 15
        reasons.append(f"{missing_ack_count} missing ACKs")
    if malformed_count >= 3:
        score += 15
        reasons.append(f"{malformed_count} malformed lines")
    if fill_before_ack_count:
        score += 20
        reasons.append(f"{fill_before_ack_count} fill-before-ACK issues")

    if score >= 50:
        level = "High"
    elif score >= 20:
        level = "Medium"
    else:
        level = "Low"

    if not reasons:
        reasons.append("No elevated operational signals detected")

    return SeverityAssessment(level=level, score=score, reasons=reasons)


def build_incident_summary(report: AnalysisReport) -> str:
    metrics = report.metrics
    severity = assess_operational_severity(report)
    dominant_reject = _dominant_item(metrics.reject_reasons)
    slow_symbol = _dominant_slow_ack_symbol(report)

    pieces = [
        f"Processed {metrics.total_orders} orders.",
        f"{metrics.rejected_count} were rejected",
    ]
    if dominant_reject:
        pieces[-1] += f", primarily due to {dominant_reject[0]}"
    pieces[-1] += "."
    pieces.append(
        f"{metrics.slow_ack_count} orders exceeded the ACK latency threshold of {report.slow_ack_ms}ms."
    )
    if slow_symbol:
        pieces.append(f"Most slow ACKs occurred in symbol {slow_symbol}.")
    pieces.append(f"Operational severity is {severity.level.lower()} ({', '.join(severity.reasons)}).")
    return " ".join(pieces)


def count_anomalies(report: AnalysisReport, anomaly_type: AnomalyType) -> int:
    return sum(1 for anomaly in report.anomalies if anomaly.anomaly_type is anomaly_type)


def unknown_event_count(report: AnalysisReport) -> int:
    return count_anomalies(report, AnomalyType.UNKNOWN_EVENT_TYPE)


def order_rows(report: AnalysisReport) -> list[dict[str, Any]]:
    rows = []
    for lifecycle in sorted(report.lifecycles.values(), key=lambda order: order.order_id):
        rows.append(
            {
                "order_id": lifecycle.order_id,
                "status": lifecycle.status.value,
                "symbol": lifecycle.symbol or "UNKNOWN",
                "side": lifecycle.side or "UNKNOWN",
                "ordered_qty": lifecycle.ordered_qty,
                "filled_qty": lifecycle.filled_qty,
                "ack_latency_ms": lifecycle.ack_latency_ms,
                "reject_reason": lifecycle.reject_reason,
                "cancel_reason": lifecycle.cancel_reason,
                "event_count": len(lifecycle.events),
            }
        )
    return rows


def anomaly_rows(report: AnalysisReport) -> list[dict[str, Any]]:
    return [
        {
            "severity": anomaly.severity.value,
            "type": anomaly.anomaly_type.value,
            "order_id": anomaly.order_id,
            "symbol": anomaly.symbol,
            "line_number": anomaly.line_number,
            "message": anomaly.message,
            "explanation": ANOMALY_EXPLANATIONS.get(anomaly.anomaly_type.value, "Review this anomaly."),
        }
        for anomaly in report.anomalies
    ]


def event_timeline_rows(report: AnalysisReport) -> list[dict[str, Any]]:
    events = sorted(
        report.parse_result.events,
        key=lambda event: (event.timestamp or datetime.min, event.line_number or 0),
    )
    return [
        {
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "order_id": event.order_id,
            "event_type": event.raw_event_type,
            "symbol": event.symbol,
            "side": event.side,
            "qty": event.qty,
            "price": event.price,
            "reason": event.reason,
            "line_number": event.line_number,
        }
        for event in events
    ]


def latency_rows(report: AnalysisReport) -> list[dict[str, Any]]:
    rows = []
    for lifecycle in report.lifecycles.values():
        if lifecycle.ack_latency_ms is None:
            continue
        rows.append(
            {
                "order_id": lifecycle.order_id,
                "symbol": lifecycle.symbol or "UNKNOWN",
                "status": lifecycle.status.value,
                "ack_latency_ms": lifecycle.ack_latency_ms,
                "is_slow": lifecycle.ack_latency_ms > report.slow_ack_ms,
            }
        )
    return sorted(rows, key=lambda row: row["ack_latency_ms"], reverse=True)


def latency_percentiles(report: AnalysisReport) -> dict[str, float | None]:
    values = sorted(row["ack_latency_ms"] for row in latency_rows(report))
    if not values:
        return {"p50": None, "p95": None, "max": None}
    return {"p50": median(values), "p95": _percentile(values, 95), "max": max(values)}


def symbol_summary_rows(report: AnalysisReport) -> list[dict[str, Any]]:
    grouped: dict[str, list[OrderLifecycle]] = {}
    for lifecycle in report.lifecycles.values():
        grouped.setdefault(lifecycle.symbol or "UNKNOWN", []).append(lifecycle)

    rows = []
    for symbol, lifecycles in sorted(grouped.items()):
        total = len(lifecycles)
        rejected = sum(1 for lifecycle in lifecycles if lifecycle.status is OrderStatus.REJECTED)
        latencies = [
            lifecycle.ack_latency_ms
            for lifecycle in lifecycles
            if lifecycle.ack_latency_ms is not None
        ]
        rows.append(
            {
                "symbol": symbol,
                "orders": total,
                "rejected": rejected,
                "reject_rate": rejected / total if total else 0,
                "average_ack_latency_ms": sum(latencies) / len(latencies) if latencies else None,
            }
        )
    return rows


def build_markdown_report(report: AnalysisReport) -> str:
    severity = assess_operational_severity(report)
    lines = [
        "# TradeOps Analysis Report",
        "",
        f"- Source file: `{report.source_file}`",
        f"- Input format: `{report.input_format}`",
        f"- Slow ACK threshold: `{report.slow_ack_ms}ms`",
        f"- Operational severity: **{severity.level}**",
        "",
        "## Incident Summary",
        "",
        build_incident_summary(report),
        "",
        "## Metrics",
        "",
        f"- Total orders: {report.metrics.total_orders}",
        f"- Filled orders: {report.metrics.filled_count}",
        f"- Rejected orders: {report.metrics.rejected_count}",
        f"- Canceled orders: {report.metrics.canceled_count}",
        f"- Open/incomplete orders: {report.metrics.open_incomplete_count}",
        f"- Average ACK latency: {_format_ms(report.metrics.average_ack_latency_ms)}",
        f"- Slow ACK count: {report.metrics.slow_ack_count}",
        f"- Malformed line count: {report.parse_result.malformed_count}",
        f"- Unknown event count: {unknown_event_count(report)}",
        "",
        "## Top Anomalies",
        "",
    ]
    if report.anomalies:
        for anomaly in report.anomalies[:10]:
            lines.append(f"- [{anomaly.severity.value}] {anomaly.anomaly_type.value}: {anomaly.message}")
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def build_json_export(report: AnalysisReport) -> str:
    payload = report.to_dict(include_orders=True)
    payload["incident_summary"] = build_incident_summary(report)
    payload["operational_severity"] = assess_operational_severity(report).to_dict()
    payload["latency_percentiles"] = latency_percentiles(report)
    payload["symbols"] = symbol_summary_rows(report)
    return json.dumps(payload, indent=2, sort_keys=True)


def report_filename(source_file: str, suffix: str) -> str:
    stem = Path(source_file).stem or "analysis"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{stem}_summary.{suffix}"


def _dominant_item(counts: dict[str, int]) -> tuple[str, int] | None:
    if not counts:
        return None
    return max(counts.items(), key=lambda item: item[1])


def _dominant_slow_ack_symbol(report: AnalysisReport) -> str | None:
    slow_rows = [row for row in latency_rows(report) if row["is_slow"]]
    if not slow_rows:
        return None
    counts: dict[str, int] = {}
    for row in slow_rows:
        counts[row["symbol"]] = counts.get(row["symbol"], 0) + 1
    return max(counts.items(), key=lambda item: item[1])[0]


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        raise ValueError("Cannot calculate percentile for an empty list.")
    if len(values) == 1:
        return values[0]
    rank = (len(values) - 1) * (percentile / 100)
    lower = int(rank)
    upper = min(lower + 1, len(values) - 1)
    weight = rank - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def _format_ms(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}ms"
