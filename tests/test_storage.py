"""SQLite persistence tests."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from tradeops_monitor.anomalies import detect_anomalies
from tradeops_monitor.lifecycle import reconstruct_lifecycles
from tradeops_monitor.metrics import calculate_metrics
from tradeops_monitor.models import AnalysisReport
from tradeops_monitor.parser import parse_lines
from tradeops_monitor.storage import list_recent_runs, store_report


class StorageTests(unittest.TestCase):
    def test_store_report_persists_run_orders_events_and_anomalies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "tradeops.db"
            report = _build_report()

            run_id = store_report(db_path, report)

            self.assertEqual(run_id, 1)
            with closing(sqlite3.connect(db_path)) as connection:
                run_count = connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                order_count = connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
                event_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                anomaly_count = connection.execute("SELECT COUNT(*) FROM anomalies").fetchone()[0]

            self.assertEqual(run_count, 1)
            self.assertEqual(order_count, 2)
            self.assertEqual(event_count, 4)
            self.assertGreaterEqual(anomaly_count, 1)

    def test_list_recent_runs_returns_stored_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "tradeops.db"
            store_report(db_path, _build_report())

            runs = list_recent_runs(db_path)

            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0].run_id, 1)
            self.assertEqual(runs[0].source_file, "sample.log")
            self.assertEqual(runs[0].input_format, "plain")
            self.assertEqual(runs[0].total_orders, 2)


def _build_report() -> AnalysisReport:
    parse_result = parse_lines(
        [
            "2026-05-19T09:30:00.000 ORDER_NEW id=ORD1 symbol=ES side=BUY qty=1",
            "2026-05-19T09:30:00.600 ORDER_ACK id=ORD1",
            "2026-05-19T09:31:00.000 ORDER_NEW id=ORD2 symbol=NQ side=SELL qty=1",
            "2026-05-19T09:31:00.100 ORDER_REJECT id=ORD2 reason=RISK_LIMIT",
        ]
    )
    lifecycles = reconstruct_lifecycles(parse_result.events)
    metrics = calculate_metrics(lifecycles.values(), slow_ack_ms=250)
    anomalies = detect_anomalies(parse_result, lifecycles.values(), slow_ack_ms=250)
    return AnalysisReport(
        source_file="sample.log",
        input_format="plain",
        slow_ack_ms=250,
        parse_result=parse_result,
        lifecycles=lifecycles,
        metrics=metrics,
        anomalies=anomalies,
    )
