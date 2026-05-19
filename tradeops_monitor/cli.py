"""Command-line interface for TradeOps Log Monitor."""

from __future__ import annotations

import argparse


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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    parser.error("CLI implementation is not available yet.")
    return 1

