"""Shared analysis service tests."""

from __future__ import annotations

import unittest

from tradeops_monitor.services import build_analysis_report_from_lines


class ServiceTests(unittest.TestCase):
    def test_build_analysis_report_from_lines_reuses_core_pipeline(self) -> None:
        report = build_analysis_report_from_lines(
            lines=[
                "2026-05-19T09:30:00.000 ORDER_NEW id=ORD1 symbol=ES side=BUY qty=1",
                "2026-05-19T09:30:00.100 ORDER_ACK id=ORD1",
                "2026-05-19T09:30:00.200 ORDER_FILL id=ORD1 qty=1 price=5280.00",
            ],
            source_file="inline.log",
            input_format="plain",
            slow_ack_ms=250,
        )

        self.assertEqual(report.source_file, "inline.log")
        self.assertEqual(report.metrics.total_orders, 1)
        self.assertEqual(report.metrics.filled_count, 1)
        self.assertEqual(report.anomalies, [])

    def test_build_analysis_report_filters_symbol(self) -> None:
        report = build_analysis_report_from_lines(
            lines=[
                "2026-05-19T09:30:00.000 ORDER_NEW id=ORD1 symbol=ES side=BUY qty=1",
                "2026-05-19T09:30:00.100 ORDER_ACK id=ORD1",
                "2026-05-19T09:31:00.000 ORDER_NEW id=ORD2 symbol=NQ side=SELL qty=1",
                "2026-05-19T09:31:00.100 ORDER_ACK id=ORD2",
            ],
            source_file="inline.log",
            input_format="plain",
            slow_ack_ms=250,
            symbol="ES",
        )

        self.assertEqual(report.metrics.total_orders, 1)
        self.assertEqual(set(report.lifecycles), {"ORD1"})

    def test_build_analysis_report_rejects_invalid_threshold(self) -> None:
        with self.assertRaises(ValueError):
            build_analysis_report_from_lines(
                lines=[],
                source_file="inline.log",
                input_format="plain",
                slow_ack_ms=0,
            )

