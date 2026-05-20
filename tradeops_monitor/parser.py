"""Parsing utilities for local order event logs."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import AnomalySeverity, EventType, OrderEvent, ParseIssue, ParseResult


SUPPORTED_FORMATS = {"plain", "json", "csv"}


def parse_log_file(path: str | Path, log_format: str = "plain") -> ParseResult:
    file_path = Path(path)
    if log_format not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported log format: {log_format}")
    if not file_path.exists():
        raise FileNotFoundError(f"Log file not found: {file_path}")
    if not file_path.is_file():
        raise IsADirectoryError(f"Log path is not a file: {file_path}")

    with file_path.open("r", encoding="utf-8", newline="") as handle:
        return parse_lines(handle, log_format=log_format)


def parse_lines(lines: Iterable[str], log_format: str = "plain") -> ParseResult:
    if log_format == "plain":
        return _parse_plain_lines(lines)
    if log_format == "json":
        return _parse_json_lines(lines)
    if log_format == "csv":
        return _parse_csv_lines(lines)
    raise ValueError(f"Unsupported log format: {log_format}")


def _parse_plain_lines(lines: Iterable[str]) -> ParseResult:
    events: list[OrderEvent] = []
    issues: list[ParseIssue] = []

    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        event, line_issues = _parse_plain_line(raw_line, line_number)
        issues.extend(line_issues)
        if event:
            events.append(event)

    return ParseResult(events=events, issues=issues)


def _parse_plain_line(raw_line: str, line_number: int) -> tuple[OrderEvent | None, list[ParseIssue]]:
    pieces = raw_line.split()
    if len(pieces) < 2:
        return None, [
            ParseIssue(
                line_number=line_number,
                message="Line must include an ISO timestamp and event type.",
                raw_line=raw_line,
                severity=AnomalySeverity.CRITICAL,
            )
        ]

    timestamp = _parse_timestamp(pieces[0])
    if timestamp is None:
        return None, [
            ParseIssue(
                line_number=line_number,
                message=f"Invalid timestamp: {pieces[0]}",
                raw_line=raw_line,
                severity=AnomalySeverity.CRITICAL,
            )
        ]

    raw_event_type = pieces[1]
    fields, field_issues = _parse_key_value_fields(pieces[2:], raw_line, line_number)
    event, event_issues = _build_event(
        timestamp=timestamp,
        raw_event_type=raw_event_type,
        fields=fields,
        line_number=line_number,
        raw_line=raw_line,
        source_format="plain",
    )
    return event, field_issues + event_issues


def _parse_json_lines(lines: Iterable[str]) -> ParseResult:
    events: list[OrderEvent] = []
    issues: list[ParseIssue] = []

    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            issues.append(
                ParseIssue(
                    line_number=line_number,
                    message=f"Invalid JSON: {exc.msg}",
                    raw_line=raw_line,
                    severity=AnomalySeverity.CRITICAL,
                )
            )
            continue
        if not isinstance(payload, dict):
            issues.append(
                ParseIssue(
                    line_number=line_number,
                    message="JSON log rows must be objects.",
                    raw_line=raw_line,
                    severity=AnomalySeverity.CRITICAL,
                )
            )
            continue

        event, row_issues = _event_from_mapping(
            payload,
            line_number=line_number,
            raw_line=raw_line,
            source_format="json",
        )
        issues.extend(row_issues)
        if event:
            events.append(event)

    return ParseResult(events=events, issues=issues)


def _parse_csv_lines(lines: Iterable[str]) -> ParseResult:
    events: list[OrderEvent] = []
    issues: list[ParseIssue] = []
    reader = csv.DictReader(lines)
    for row in reader:
        line_number = reader.line_num
        event, row_issues = _event_from_mapping(
            {key: value for key, value in row.items() if key is not None},
            line_number=line_number,
            raw_line="",
            source_format="csv",
        )
        issues.extend(row_issues)
        if event:
            events.append(event)

    return ParseResult(events=events, issues=issues)


def _event_from_mapping(
    row: dict[str, object],
    *,
    line_number: int,
    raw_line: str,
    source_format: str,
) -> tuple[OrderEvent | None, list[ParseIssue]]:
    timestamp_value = _first_present(row, "timestamp", "time", "ts")
    raw_event_type = _first_present(row, "event_type", "event", "type")
    issues: list[ParseIssue] = []

    if not timestamp_value:
        return None, [
            ParseIssue(
                line_number=line_number,
                message="Missing timestamp field.",
                raw_line=raw_line,
                severity=AnomalySeverity.CRITICAL,
            )
        ]
    if not raw_event_type:
        return None, [
            ParseIssue(
                line_number=line_number,
                message="Missing event type field.",
                raw_line=raw_line,
                severity=AnomalySeverity.CRITICAL,
            )
        ]

    timestamp = _parse_timestamp(str(timestamp_value))
    if timestamp is None:
        return None, [
            ParseIssue(
                line_number=line_number,
                message=f"Invalid timestamp: {timestamp_value}",
                raw_line=raw_line,
                severity=AnomalySeverity.CRITICAL,
            )
        ]

    fields = {
        str(key): str(value)
        for key, value in row.items()
        if value not in (None, "") and str(key) not in {"timestamp", "time", "ts", "event_type", "event", "type"}
    }
    event, event_issues = _build_event(
        timestamp=timestamp,
        raw_event_type=str(raw_event_type),
        fields=fields,
        line_number=line_number,
        raw_line=raw_line,
        source_format=source_format,
    )
    issues.extend(event_issues)
    return event, issues


def _build_event(
    *,
    timestamp: datetime,
    raw_event_type: str,
    fields: dict[str, str],
    line_number: int,
    raw_line: str,
    source_format: str,
) -> tuple[OrderEvent, list[ParseIssue]]:
    event_type = EventType.from_raw(raw_event_type)
    issues: list[ParseIssue] = []

    order_id = fields.get("id") or fields.get("order_id")
    if not order_id:
        issues.append(
            ParseIssue(
                line_number=line_number,
                message="Missing order id field.",
                raw_line=raw_line,
                severity=AnomalySeverity.CRITICAL,
            )
        )

    if event_type is EventType.UNKNOWN:
        issues.append(
            ParseIssue(
                line_number=line_number,
                message=f"Unknown event type: {raw_event_type}",
                raw_line=raw_line,
            )
        )

    qty, qty_issue = _parse_optional_int(fields.get("qty"), "qty", raw_line, line_number)
    price, price_issue = _parse_optional_float(fields.get("price"), "price", raw_line, line_number)
    if qty_issue:
        issues.append(qty_issue)
    if price_issue:
        issues.append(price_issue)

    return (
        OrderEvent(
            timestamp=timestamp,
            event_type=event_type,
            raw_event_type=raw_event_type,
            order_id=order_id,
            symbol=fields.get("symbol"),
            side=fields.get("side"),
            qty=qty,
            price=price,
            reason=fields.get("reason"),
            fields=fields,
            line_number=line_number,
            raw_line=raw_line,
            source_format=source_format,
        ),
        issues,
    )


def _parse_key_value_fields(
    tokens: list[str],
    raw_line: str,
    line_number: int,
) -> tuple[dict[str, str], list[ParseIssue]]:
    fields: dict[str, str] = {}
    issues: list[ParseIssue] = []

    for token in tokens:
        if "=" not in token:
            issues.append(
                ParseIssue(
                    line_number=line_number,
                    message=f"Malformed field token: {token}",
                    raw_line=raw_line,
                )
            )
            continue
        key, value = token.split("=", 1)
        if not key:
            issues.append(
                ParseIssue(
                    line_number=line_number,
                    message=f"Malformed field token: {token}",
                    raw_line=raw_line,
                )
            )
            continue
        fields[key] = value

    return fields, issues


def _parse_timestamp(raw_value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return None


def _parse_optional_int(
    raw_value: str | None,
    field_name: str,
    raw_line: str,
    line_number: int,
) -> tuple[int | None, ParseIssue | None]:
    if raw_value in (None, ""):
        return None, None
    try:
        return int(raw_value), None
    except ValueError:
        return None, ParseIssue(
            line_number=line_number,
            message=f"Invalid integer for {field_name}: {raw_value}",
            raw_line=raw_line,
        )


def _parse_optional_float(
    raw_value: str | None,
    field_name: str,
    raw_line: str,
    line_number: int,
) -> tuple[float | None, ParseIssue | None]:
    if raw_value in (None, ""):
        return None, None
    try:
        return float(raw_value), None
    except ValueError:
        return None, ParseIssue(
            line_number=line_number,
            message=f"Invalid number for {field_name}: {raw_value}",
            raw_line=raw_line,
        )


def _first_present(row: dict[str, object], *keys: str) -> object | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None
