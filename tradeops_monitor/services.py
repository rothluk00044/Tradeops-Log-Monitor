"""Shared analysis services used by the CLI and dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .anomalies import detect_anomalies
from .lifecycle import reconstruct_lifecycles
from .metrics import calculate_metrics
from .models import AnalysisReport, OrderLifecycle, ParseResult
from .parser import parse_lines, parse_log_file


def build_analysis_report(
    *,
    file_path: str | Path,
    input_format: str,
    slow_ack_ms: int,
    symbol: str | None = None,
) -> AnalysisReport:
    parse_result = parse_log_file(file_path, log_format=input_format)
    return build_analysis_report_from_parse_result(
        parse_result=parse_result,
        source_file=str(file_path),
        input_format=input_format,
        slow_ack_ms=slow_ack_ms,
        symbol=symbol,
    )


def build_analysis_report_from_lines(
    *,
    lines: Iterable[str],
    source_file: str,
    input_format: str,
    slow_ack_ms: int,
    symbol: str | None = None,
) -> AnalysisReport:
    parse_result = parse_lines(lines, log_format=input_format)
    return build_analysis_report_from_parse_result(
        parse_result=parse_result,
        source_file=source_file,
        input_format=input_format,
        slow_ack_ms=slow_ack_ms,
        symbol=symbol,
    )


def build_analysis_report_from_parse_result(
    *,
    parse_result: ParseResult,
    source_file: str,
    input_format: str,
    slow_ack_ms: int,
    symbol: str | None = None,
) -> AnalysisReport:
    if slow_ack_ms <= 0:
        raise ValueError("--slow-ack-ms must be greater than zero.")

    lifecycles = reconstruct_lifecycles(parse_result.events)
    if symbol:
        lifecycles = filter_lifecycles_by_symbol(lifecycles, symbol)
        parse_result = filter_parse_result_by_order_ids(parse_result, set(lifecycles))

    metrics = calculate_metrics(lifecycles.values(), slow_ack_ms=slow_ack_ms)
    anomalies = detect_anomalies(parse_result, lifecycles.values(), slow_ack_ms=slow_ack_ms)
    return AnalysisReport(
        source_file=source_file,
        input_format=input_format,
        slow_ack_ms=slow_ack_ms,
        parse_result=parse_result,
        lifecycles=lifecycles,
        metrics=metrics,
        anomalies=anomalies,
    )


def filter_lifecycles_by_symbol(
    lifecycles: dict[str, OrderLifecycle],
    symbol: str,
) -> dict[str, OrderLifecycle]:
    normalized_symbol = symbol.upper()
    return {
        order_id: lifecycle
        for order_id, lifecycle in lifecycles.items()
        if lifecycle.symbol and lifecycle.symbol.upper() == normalized_symbol
    }


def filter_parse_result_by_order_ids(parse_result: ParseResult, order_ids: set[str]) -> ParseResult:
    return ParseResult(
        events=[event for event in parse_result.events if event.order_id in order_ids],
        issues=parse_result.issues,
    )
