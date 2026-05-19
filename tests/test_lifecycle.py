"""Lifecycle reconstruction tests."""

from __future__ import annotations

import unittest

from tradeops_monitor.lifecycle import reconstruct_lifecycles
from tradeops_monitor.models import OrderStatus
from tradeops_monitor.parser import parse_lines


class LifecycleTests(unittest.TestCase):
    def test_reconstructs_filled_order_with_ack_latency(self) -> None:
        result = parse_lines(
            [
                "2026-05-19T09:30:01.125 ORDER_NEW id=ORD123 symbol=ES side=BUY qty=2",
                "2026-05-19T09:30:01.220 ORDER_ACK id=ORD123",
                "2026-05-19T09:30:02.000 ORDER_FILL id=ORD123 qty=2 price=5280.25",
            ]
        )

        lifecycle = reconstruct_lifecycles(result.events)["ORD123"]

        self.assertEqual(lifecycle.status, OrderStatus.FILLED)
        self.assertEqual(lifecycle.symbol, "ES")
        self.assertEqual(lifecycle.side, "BUY")
        self.assertEqual(lifecycle.ordered_qty, 2)
        self.assertEqual(lifecycle.filled_qty, 2)
        self.assertEqual(lifecycle.ack_latency_ms, 95.0)

    def test_reconstructs_partially_filled_order(self) -> None:
        result = parse_lines(
            [
                "2026-05-19T09:30:01.000 ORDER_NEW id=ORD124 symbol=NQ side=SELL qty=3",
                "2026-05-19T09:30:01.080 ORDER_ACK id=ORD124",
                "2026-05-19T09:30:02.000 ORDER_FILL id=ORD124 qty=1 price=18420.25",
            ]
        )

        lifecycle = reconstruct_lifecycles(result.events)["ORD124"]

        self.assertEqual(lifecycle.status, OrderStatus.PARTIALLY_FILLED)
        self.assertEqual(lifecycle.filled_qty, 1)

    def test_multiple_fills_can_complete_order(self) -> None:
        result = parse_lines(
            [
                "2026-05-19T09:30:01.000 ORDER_NEW id=ORD125 symbol=YM side=BUY qty=3",
                "2026-05-19T09:30:01.050 ORDER_ACK id=ORD125",
                "2026-05-19T09:30:02.000 ORDER_FILL id=ORD125 qty=1 price=39750.00",
                "2026-05-19T09:30:03.000 ORDER_FILL id=ORD125 qty=2 price=39751.00",
            ]
        )

        lifecycle = reconstruct_lifecycles(result.events)["ORD125"]

        self.assertEqual(lifecycle.status, OrderStatus.FILLED)
        self.assertEqual(lifecycle.filled_qty, 3)

    def test_reconstructs_rejected_order(self) -> None:
        result = parse_lines(
            [
                "2026-05-19T09:31:15.100 ORDER_NEW id=ORD126 symbol=NQ side=SELL qty=1",
                "2026-05-19T09:31:15.900 ORDER_REJECT id=ORD126 reason=RISK_LIMIT",
            ]
        )

        lifecycle = reconstruct_lifecycles(result.events)["ORD126"]

        self.assertEqual(lifecycle.status, OrderStatus.REJECTED)
        self.assertEqual(lifecycle.reject_reason, "RISK_LIMIT")

    def test_reconstructs_canceled_order(self) -> None:
        result = parse_lines(
            [
                "2026-05-19T09:31:15.100 ORDER_NEW id=ORD127 symbol=NQ side=SELL qty=1",
                "2026-05-19T09:31:15.250 ORDER_ACK id=ORD127",
                "2026-05-19T09:31:15.700 ORDER_CANCEL id=ORD127 reason=USER_REQUEST",
            ]
        )

        lifecycle = reconstruct_lifecycles(result.events)["ORD127"]

        self.assertEqual(lifecycle.status, OrderStatus.CANCELED)
        self.assertEqual(lifecycle.cancel_reason, "USER_REQUEST")

    def test_event_without_new_is_incomplete(self) -> None:
        result = parse_lines(["2026-05-19T09:32:01.000 ORDER_FILL id=ORD128 qty=1 price=5281.00"])

        lifecycle = reconstruct_lifecycles(result.events)["ORD128"]

        self.assertEqual(lifecycle.status, OrderStatus.INCOMPLETE)
        self.assertEqual(lifecycle.filled_qty, 1)

    def test_events_are_sorted_by_timestamp(self) -> None:
        result = parse_lines(
            [
                "2026-05-19T09:30:01.220 ORDER_ACK id=ORD129",
                "2026-05-19T09:30:01.125 ORDER_NEW id=ORD129 symbol=ES side=BUY qty=2",
            ]
        )

        lifecycle = reconstruct_lifecycles(result.events)["ORD129"]

        self.assertEqual([event.event_type.value for event in lifecycle.events], ["ORDER_NEW", "ORDER_ACK"])
