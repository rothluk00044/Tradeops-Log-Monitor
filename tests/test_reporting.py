"""Reporting helper tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tradeops_monitor.reporting import (
    assess_operational_severity,
    build_incident_summary,
    build_json_export,
    build_markdown_report,
    latency_percentiles,
    order_rows,
    save_report_exports,
    symbol_summary_rows,
    unknown_event_count,
)
from tradeops_monitor.services import build_analysis_report_from_lines


class ReportingTests(unittest.TestCase):
    def test_incident_summary_and_severity_are_deterministic(self) -> None:
        report = _sample_report()

        summary = build_incident_summary(report)
        severity = assess_operational_severity(report)

        self.assertIn("Processed 4 orders", summary)
        self.assertIn("RISK_LIMIT", summary)
        self.assertEqual(severity.level, "High")
        self.assertGreater(severity.score, 0)

    def test_latency_percentiles(self) -> None:
        report = _sample_report()

        percentiles = latency_percentiles(report)

        self.assertEqual(percentiles["p50"], 400.0)
        self.assertGreaterEqual(percentiles["p95"], 570.0)
        self.assertEqual(percentiles["max"], 600.0)

    def test_symbol_summary_rows_include_reject_rate_and_latency(self) -> None:
        report = _sample_report()

        rows = {row["symbol"]: row for row in symbol_summary_rows(report)}

        self.assertEqual(rows["NQ"]["orders"], 2)
        self.assertEqual(rows["NQ"]["rejected"], 2)
        self.assertEqual(rows["NQ"]["reject_rate"], 1.0)
        self.assertEqual(rows["ES"]["average_ack_latency_ms"], 600.0)

    def test_export_helpers_include_summary_data(self) -> None:
        report = _sample_report()

        markdown = build_markdown_report(report)
        payload = json.loads(build_json_export(report))

        self.assertIn("# TradeOps Analysis Report", markdown)
        self.assertIn("incident_summary", payload)
        self.assertIn("operational_severity", payload)
        self.assertEqual(len(order_rows(report)), 4)
        self.assertEqual(unknown_event_count(report), 0)

    def test_save_report_exports_writes_markdown_and_json(self) -> None:
        report = _sample_report()

        with tempfile.TemporaryDirectory() as temp_dir:
            markdown_path, json_path = save_report_exports(report, Path(temp_dir))

            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())
            self.assertIn("TradeOps Analysis Report", markdown_path.read_text(encoding="utf-8"))
            self.assertIn("incident_summary", json_path.read_text(encoding="utf-8"))


def _sample_report():
    return build_analysis_report_from_lines(
        lines=[
            "2026-05-19T09:30:00.000 ORDER_NEW id=ORD1 symbol=ES side=BUY qty=1",
            "2026-05-19T09:30:00.600 ORDER_ACK id=ORD1",
            "2026-05-19T09:30:00.800 ORDER_FILL id=ORD1 qty=1 price=5280.00",
            "2026-05-19T09:31:00.000 ORDER_NEW id=ORD2 symbol=NQ side=SELL qty=1",
            "2026-05-19T09:31:00.100 ORDER_REJECT id=ORD2 reason=RISK_LIMIT",
            "2026-05-19T09:32:00.000 ORDER_NEW id=ORD3 symbol=NQ side=SELL qty=1",
            "2026-05-19T09:32:00.100 ORDER_REJECT id=ORD3 reason=RISK_LIMIT",
            "2026-05-19T09:33:00.000 ORDER_NEW id=ORD4 symbol=CL side=BUY qty=1",
            "2026-05-19T09:33:00.100 ORDER_FILL id=ORD4 qty=1 price=79.25",
            "2026-05-19T09:33:00.200 ORDER_ACK id=ORD4",
        ],
        source_file="sample.log",
        input_format="plain",
        slow_ack_ms=250,
    )
