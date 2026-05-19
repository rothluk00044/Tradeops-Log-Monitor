"""Metric calculation tests."""

from __future__ import annotations

import unittest

from tradeops_monitor.lifecycle import reconstruct_lifecycles
from tradeops_monitor.metrics import calculate_metrics
from tradeops_monitor.parser import parse_lines


class MetricsTests(unittest.TestCase):
    def test_calculates_counts_and_ack_latency_metrics(self) -> None:
        result = parse_lines(
            [
                "2026-05-19T09:30:00.000 ORDER_NEW id=ORD1 symbol=ES side=BUY qty=1",
                "2026-05-19T09:30:00.100 ORDER_ACK id=ORD1",
                "2026-05-19T09:30:00.300 ORDER_FILL id=ORD1 qty=1 price=5280.00",
                "2026-05-19T09:31:00.000 ORDER_NEW id=ORD2 symbol=NQ side=SELL qty=1",
                "2026-05-19T09:31:00.800 ORDER_REJECT id=ORD2 reason=RISK_LIMIT",
                "2026-05-19T09:32:00.000 ORDER_NEW id=ORD3 symbol=ES side=BUY qty=2",
                "2026-05-19T09:32:00.400 ORDER_ACK id=ORD3",
                "2026-05-19T09:32:00.900 ORDER_CANCEL id=ORD3 reason=USER_REQUEST",
                "2026-05-19T09:33:00.000 ORDER_NEW id=ORD4 symbol=CL side=BUY qty=3",
                "2026-05-19T09:33:00.100 ORDER_ACK id=ORD4",
                "2026-05-19T09:33:00.400 ORDER_FILL id=ORD4 qty=1 price=79.35",
            ]
        )
        lifecycles = reconstruct_lifecycles(result.events)

        metrics = calculate_metrics(lifecycles.values(), slow_ack_ms=250)

        self.assertEqual(metrics.total_orders, 4)
        self.assertEqual(metrics.filled_count, 1)
        self.assertEqual(metrics.rejected_count, 1)
        self.assertEqual(metrics.canceled_count, 1)
        self.assertEqual(metrics.open_incomplete_count, 1)
        self.assertEqual(metrics.slow_ack_count, 1)
        self.assertEqual(metrics.average_ack_latency_ms, 200.0)
        self.assertEqual(metrics.min_ack_latency_ms, 100.0)
        self.assertEqual(metrics.max_ack_latency_ms, 400.0)
        self.assertEqual(metrics.reject_reasons, {"RISK_LIMIT": 1})
        self.assertEqual(metrics.counts_by_symbol, {"CL": 1, "ES": 2, "NQ": 1})
        self.assertEqual(metrics.counts_by_side, {"BUY": 3, "SELL": 1})

    def test_empty_lifecycle_metrics_are_zeroed(self) -> None:
        metrics = calculate_metrics([], slow_ack_ms=250)

        self.assertEqual(metrics.total_orders, 0)
        self.assertEqual(metrics.filled_count, 0)
        self.assertIsNone(metrics.average_ack_latency_ms)
        self.assertEqual(metrics.reject_reasons, {})
        self.assertEqual(metrics.counts_by_symbol, {})

    def test_reject_reason_defaults_when_missing(self) -> None:
        result = parse_lines(
            [
                "2026-05-19T09:30:00.000 ORDER_NEW id=ORD1 symbol=ES side=BUY qty=1",
                "2026-05-19T09:30:00.100 ORDER_REJECT id=ORD1",
            ]
        )

        metrics = calculate_metrics(reconstruct_lifecycles(result.events).values())

        self.assertEqual(metrics.reject_reasons, {"UNKNOWN": 1})
