"""Parser tests."""

from __future__ import annotations

from pathlib import Path
import unittest

from tradeops_monitor.models import EventType
from tradeops_monitor.parser import parse_lines, parse_log_file


class ParserTests(unittest.TestCase):
    def test_parse_plain_order_events(self) -> None:
        result = parse_lines(
            [
                "2026-05-19T09:30:01.125 ORDER_NEW id=ORD123 symbol=ES side=BUY qty=2",
                "2026-05-19T09:30:01.220 ORDER_ACK id=ORD123",
                "2026-05-19T09:30:02.000 ORDER_FILL id=ORD123 qty=2 price=5280.25",
            ]
        )

        self.assertEqual(result.issues, [])
        self.assertEqual(len(result.events), 3)
        self.assertEqual(result.events[0].event_type, EventType.ORDER_NEW)
        self.assertEqual(result.events[0].order_id, "ORD123")
        self.assertEqual(result.events[0].symbol, "ES")
        self.assertEqual(result.events[0].qty, 2)
        self.assertEqual(result.events[2].price, 5280.25)

    def test_parse_plain_reports_malformed_line(self) -> None:
        result = parse_lines(["not enough"])

        self.assertEqual(result.events, [])
        self.assertEqual(result.malformed_count, 1)
        self.assertIn("Invalid timestamp", result.issues[0].message)

    def test_parse_unknown_event_type_preserves_event(self) -> None:
        result = parse_lines(["2026-05-19T09:30:01.125 ORDER_HELD id=ORD123 symbol=ES"])

        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].event_type, EventType.UNKNOWN)
        self.assertEqual(result.events[0].raw_event_type, "ORDER_HELD")
        self.assertEqual(len(result.issues), 1)
        self.assertIn("Unknown event type", result.issues[0].message)

    def test_parse_missing_order_id_is_visible(self) -> None:
        result = parse_lines(["2026-05-19T09:30:01.125 ORDER_NEW symbol=ES side=BUY qty=2"])

        self.assertEqual(len(result.events), 1)
        self.assertIsNone(result.events[0].order_id)
        self.assertEqual(len(result.issues), 1)
        self.assertIn("Missing order id", result.issues[0].message)

    def test_parse_json_lines(self) -> None:
        result = parse_lines(
            [
                '{"timestamp":"2026-05-19T09:30:01.125","event_type":"ORDER_NEW","id":"ORD123","symbol":"ES","side":"BUY","qty":2}',
                '{"timestamp":"2026-05-19T09:30:01.220","event_type":"ORDER_ACK","id":"ORD123"}',
            ],
            log_format="json",
        )

        self.assertEqual(result.issues, [])
        self.assertEqual(
            [event.event_type for event in result.events],
            [EventType.ORDER_NEW, EventType.ORDER_ACK],
        )
        self.assertEqual(result.events[0].source_format, "json")

    def test_parse_csv_lines(self) -> None:
        result = parse_lines(
            [
                "timestamp,event_type,id,symbol,side,qty",
                "2026-05-19T09:30:01.125,ORDER_NEW,ORD123,ES,BUY,2",
                "2026-05-19T09:30:01.220,ORDER_ACK,ORD123,,,",
            ],
            log_format="csv",
        )

        self.assertEqual(result.issues, [])
        self.assertEqual(len(result.events), 2)
        self.assertEqual(result.events[0].source_format, "csv")

    def test_parse_log_file_missing_path(self) -> None:
        with self.assertRaises(FileNotFoundError):
            parse_log_file(Path("does-not-exist.log"))

    def test_empty_input_returns_no_events_or_issues(self) -> None:
        result = parse_lines([])

        self.assertEqual(result.events, [])
        self.assertEqual(result.issues, [])

    def test_invalid_numeric_fields_are_reported_without_dropping_event(self) -> None:
        result = parse_lines(
            ["2026-05-19T09:30:01.125 ORDER_FILL id=ORD123 qty=two price=bad-price"]
        )

        self.assertEqual(len(result.events), 1)
        self.assertIsNone(result.events[0].qty)
        self.assertIsNone(result.events[0].price)
        self.assertEqual(len(result.issues), 2)

    def test_malformed_key_value_token_is_visible(self) -> None:
        result = parse_lines(
            ["2026-05-19T09:30:01.125 ORDER_NEW id=ORD123 symbol=ES side BUY qty=1"]
        )

        self.assertEqual(len(result.events), 1)
        self.assertEqual(len(result.issues), 2)
        self.assertIn("Malformed field token", result.issues[0].message)

    def test_invalid_json_line_is_reported(self) -> None:
        result = parse_lines(["not-json"], log_format="json")

        self.assertEqual(result.events, [])
        self.assertEqual(len(result.issues), 1)
        self.assertIn("Invalid JSON", result.issues[0].message)
