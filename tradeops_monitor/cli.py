"""Command-line interface for TradeOps Log Monitor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .anomalies import detect_anomalies, has_critical_anomalies
from .lifecycle import reconstruct_lifecycles
from .metrics import calculate_metrics
from .models import AnalysisReport, OrderLifecycle, ParseResult
from .output import format_report, format_runs
from .parser import parse_log_file
from .storage import list_recent_runs, store_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tradeops-monitor",
        description="Parse local order-event logs and summarize order workflow health.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Analyze an order event log file.")
    analyze.add_argument("--file", required=True, help="Path to a local order event log file.")
    analyze.add_argument(
        "--format",
        choices=("plain", "json", "csv"),
        default="plain",
        help="Input log format.",
    )
    analyze.add_argument(
        "--slow-ack-ms",
        type=int,
        default=500,
        help="Slow ACK threshold in milliseconds.",
    )
    analyze.add_argument(
        "--output",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    analyze.add_argument("--symbol", help="Only include events for this symbol.")
    analyze.add_argument(
        "--show-orders",
        action="store_true",
        help="Include per-order lifecycle details in output.",
    )
    analyze.add_argument("--db", help="Optional local SQLite database path.")

    runs = subparsers.add_parser("runs", help="List recent stored analysis runs.")
    runs.add_argument("--db", required=True, help="Local SQLite database path.")
    runs.add_argument("--limit", type=int, default=10, help="Maximum number of runs to show.")
    runs.add_argument(
        "--output",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "analyze":
            return _handle_analyze(args)
        if args.command == "runs":
            return _handle_runs(args)
        parser.error(f"Unknown command: {args.command}")
    except (FileNotFoundError, IsADirectoryError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 1


def _handle_analyze(args: argparse.Namespace) -> int:
    report = build_analysis_report(
        file_path=args.file,
        input_format=args.format,
        slow_ack_ms=args.slow_ack_ms,
        symbol=args.symbol,
    )

    if args.db:
        run_id = store_report(args.db, report)
        print(f"stored analysis run #{run_id} in {args.db}", file=sys.stderr)

    sys.stdout.write(format_report(report, output_format=args.output, show_orders=args.show_orders))
    return 2 if has_critical_anomalies(report.anomalies) else 0


def _handle_runs(args: argparse.Namespace) -> int:
    if args.limit <= 0:
        raise ValueError("--limit must be greater than zero.")

    runs = list_recent_runs(args.db, limit=args.limit)
    sys.stdout.write(format_runs(runs, output_format=args.output))
    return 0


def build_analysis_report(
    *,
    file_path: str | Path,
    input_format: str,
    slow_ack_ms: int,
    symbol: str | None = None,
) -> AnalysisReport:
    if slow_ack_ms <= 0:
        raise ValueError("--slow-ack-ms must be greater than zero.")

    parse_result = parse_log_file(file_path, log_format=input_format)
    lifecycles = reconstruct_lifecycles(parse_result.events)

    if symbol:
        lifecycles = _filter_lifecycles_by_symbol(lifecycles, symbol)
        parse_result = _filter_parse_result_by_order_ids(parse_result, set(lifecycles))

    metrics = calculate_metrics(lifecycles.values(), slow_ack_ms=slow_ack_ms)
    anomalies = detect_anomalies(parse_result, lifecycles.values(), slow_ack_ms=slow_ack_ms)
    return AnalysisReport(
        source_file=str(file_path),
        input_format=input_format,
        slow_ack_ms=slow_ack_ms,
        parse_result=parse_result,
        lifecycles=lifecycles,
        metrics=metrics,
        anomalies=anomalies,
    )


def _filter_lifecycles_by_symbol(
    lifecycles: dict[str, OrderLifecycle],
    symbol: str,
) -> dict[str, OrderLifecycle]:
    normalized_symbol = symbol.upper()
    return {
        order_id: lifecycle
        for order_id, lifecycle in lifecycles.items()
        if lifecycle.symbol and lifecycle.symbol.upper() == normalized_symbol
    }


def _filter_parse_result_by_order_ids(parse_result: ParseResult, order_ids: set[str]) -> ParseResult:
    return ParseResult(
        events=[event for event in parse_result.events if event.order_id in order_ids],
        issues=parse_result.issues,
    )
