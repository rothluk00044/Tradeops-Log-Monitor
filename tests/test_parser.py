"""Parser tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from tradeops_monitor.models import EventType
from tradeops_monitor.parser import parse_lines, parse_log_file


def test_parse_plain_order_events() -> None:
    result = parse_lines(
        [
            "2026-05-19T09:30:01.125 ORDER_NEW id=ORD123 symbol=ES side=BUY qty=2",
            "2026-05-19T09:30:01.220 ORDER_ACK id=ORD123",
            "2026-05-19T09:30:02.000 ORDER_FILL id=ORD123 qty=2 price=5280.25",
        ]
    )

    assert result.issues == []
    assert len(result.events) == 3
    assert result.events[0].event_type == EventType.ORDER_NEW
    assert result.events[0].order_id == "ORD123"
    assert result.events[0].symbol == "ES"
    assert result.events[0].qty == 2
    assert result.events[2].price == 5280.25


def test_parse_plain_reports_malformed_line() -> None:
    result = parse_lines(["not enough"])

    assert result.events == []
    assert result.malformed_count == 1
    assert "Invalid timestamp" in result.issues[0].message


def test_parse_unknown_event_type_preserves_event() -> None:
    result = parse_lines(["2026-05-19T09:30:01.125 ORDER_HELD id=ORD123 symbol=ES"])

    assert len(result.events) == 1
    assert result.events[0].event_type == EventType.UNKNOWN
    assert result.events[0].raw_event_type == "ORDER_HELD"
    assert len(result.issues) == 1
    assert "Unknown event type" in result.issues[0].message


def test_parse_missing_order_id_is_visible() -> None:
    result = parse_lines(["2026-05-19T09:30:01.125 ORDER_NEW symbol=ES side=BUY qty=2"])

    assert len(result.events) == 1
    assert result.events[0].order_id is None
    assert len(result.issues) == 1
    assert "Missing order id" in result.issues[0].message


def test_parse_json_lines() -> None:
    result = parse_lines(
        [
            '{"timestamp":"2026-05-19T09:30:01.125","event_type":"ORDER_NEW","id":"ORD123","symbol":"ES","side":"BUY","qty":2}',
            '{"timestamp":"2026-05-19T09:30:01.220","event_type":"ORDER_ACK","id":"ORD123"}',
        ],
        log_format="json",
    )

    assert result.issues == []
    assert [event.event_type for event in result.events] == [EventType.ORDER_NEW, EventType.ORDER_ACK]
    assert result.events[0].source_format == "json"


def test_parse_csv_lines() -> None:
    result = parse_lines(
        [
            "timestamp,event_type,id,symbol,side,qty",
            "2026-05-19T09:30:01.125,ORDER_NEW,ORD123,ES,BUY,2",
            "2026-05-19T09:30:01.220,ORDER_ACK,ORD123,,,",
        ],
        log_format="csv",
    )

    assert result.issues == []
    assert len(result.events) == 2
    assert result.events[0].source_format == "csv"


def test_parse_log_file_missing_path() -> None:
    with pytest.raises(FileNotFoundError):
        parse_log_file(Path("does-not-exist.log"))
