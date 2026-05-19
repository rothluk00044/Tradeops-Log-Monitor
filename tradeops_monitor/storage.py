"""Optional SQLite persistence for analysis runs."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import AnalysisReport, AnomalySeverity, StoredRun


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source_file TEXT NOT NULL,
    input_format TEXT NOT NULL,
    slow_ack_ms INTEGER NOT NULL,
    total_orders INTEGER NOT NULL,
    filled_count INTEGER NOT NULL,
    rejected_count INTEGER NOT NULL,
    canceled_count INTEGER NOT NULL,
    open_incomplete_count INTEGER NOT NULL,
    anomaly_count INTEGER NOT NULL,
    critical_anomaly_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    run_id INTEGER NOT NULL,
    order_id TEXT NOT NULL,
    status TEXT NOT NULL,
    symbol TEXT,
    side TEXT,
    ordered_qty INTEGER,
    filled_qty INTEGER NOT NULL,
    ack_latency_ms REAL,
    reject_reason TEXT,
    cancel_reason TEXT,
    PRIMARY KEY (run_id, order_id),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    order_id TEXT,
    timestamp TEXT,
    event_type TEXT NOT NULL,
    raw_event_type TEXT NOT NULL,
    symbol TEXT,
    side TEXT,
    qty INTEGER,
    price REAL,
    reason TEXT,
    line_number INTEGER,
    raw_line TEXT,
    fields_json TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS anomalies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    order_id TEXT,
    symbol TEXT,
    line_number INTEGER,
    details_json TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);
"""


def initialize_database(db_path: str | Path) -> None:
    path = Path(db_path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)


def store_report(db_path: str | Path, report: AnalysisReport) -> int:
    initialize_database(db_path)
    with sqlite3.connect(db_path) as connection:
        run_id = _insert_run(connection, report)
        _insert_orders(connection, run_id, report)
        _insert_events(connection, run_id, report)
        _insert_anomalies(connection, run_id, report)
        connection.commit()
        return run_id


def list_recent_runs(db_path: str | Path, *, limit: int = 10) -> list[StoredRun]:
    initialize_database(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, created_at, source_file, input_format, total_orders, anomaly_count, critical_anomaly_count
            FROM runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        StoredRun(
            run_id=row["id"],
            created_at=row["created_at"],
            source_file=row["source_file"],
            input_format=row["input_format"],
            total_orders=row["total_orders"],
            anomaly_count=row["anomaly_count"],
            critical_anomaly_count=row["critical_anomaly_count"],
        )
        for row in rows
    ]


def _insert_run(connection: sqlite3.Connection, report: AnalysisReport) -> int:
    critical_count = sum(1 for anomaly in report.anomalies if anomaly.severity is AnomalySeverity.CRITICAL)
    cursor = connection.execute(
        """
        INSERT INTO runs (
            created_at,
            source_file,
            input_format,
            slow_ack_ms,
            total_orders,
            filled_count,
            rejected_count,
            canceled_count,
            open_incomplete_count,
            anomaly_count,
            critical_anomaly_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            report.source_file,
            report.input_format,
            report.slow_ack_ms,
            report.metrics.total_orders,
            report.metrics.filled_count,
            report.metrics.rejected_count,
            report.metrics.canceled_count,
            report.metrics.open_incomplete_count,
            len(report.anomalies),
            critical_count,
        ),
    )
    return int(cursor.lastrowid)


def _insert_orders(connection: sqlite3.Connection, run_id: int, report: AnalysisReport) -> None:
    connection.executemany(
        """
        INSERT INTO orders (
            run_id,
            order_id,
            status,
            symbol,
            side,
            ordered_qty,
            filled_qty,
            ack_latency_ms,
            reject_reason,
            cancel_reason
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                run_id,
                lifecycle.order_id,
                lifecycle.status.value,
                lifecycle.symbol,
                lifecycle.side,
                lifecycle.ordered_qty,
                lifecycle.filled_qty,
                lifecycle.ack_latency_ms,
                lifecycle.reject_reason,
                lifecycle.cancel_reason,
            )
            for lifecycle in report.lifecycles.values()
        ],
    )


def _insert_events(connection: sqlite3.Connection, run_id: int, report: AnalysisReport) -> None:
    connection.executemany(
        """
        INSERT INTO events (
            run_id,
            order_id,
            timestamp,
            event_type,
            raw_event_type,
            symbol,
            side,
            qty,
            price,
            reason,
            line_number,
            raw_line,
            fields_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                run_id,
                event.order_id,
                event.timestamp.isoformat() if event.timestamp else None,
                event.event_type.value,
                event.raw_event_type,
                event.symbol,
                event.side,
                event.qty,
                event.price,
                event.reason,
                event.line_number,
                event.raw_line,
                json.dumps(event.fields, sort_keys=True),
            )
            for event in report.parse_result.events
        ],
    )


def _insert_anomalies(connection: sqlite3.Connection, run_id: int, report: AnalysisReport) -> None:
    connection.executemany(
        """
        INSERT INTO anomalies (
            run_id,
            type,
            severity,
            message,
            order_id,
            symbol,
            line_number,
            details_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                run_id,
                anomaly.anomaly_type.value,
                anomaly.severity.value,
                anomaly.message,
                anomaly.order_id,
                anomaly.symbol,
                anomaly.line_number,
                json.dumps(anomaly.details, sort_keys=True),
            )
            for anomaly in report.anomalies
        ],
    )
