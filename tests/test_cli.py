"""CLI smoke tests."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tradeops_monitor.cli import main


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_analyze_text_output_returns_success_for_basic_log(self) -> None:
        exit_code, stdout, stderr = _run_cli(
            [
                "analyze",
                "--file",
                str(ROOT / "sample_logs" / "orders_basic.log"),
                "--show-orders",
            ]
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("TradeOps Log Monitor Summary", stdout)
        self.assertIn("- Total orders: 3", stdout)
        self.assertIn("ORD100: status=FILLED", stdout)

    def test_analyze_json_output_returns_critical_anomaly_exit_code(self) -> None:
        exit_code, stdout, stderr = _run_cli(
            [
                "analyze",
                "--file",
                str(ROOT / "sample_logs" / "orders_anomalies.log"),
                "--slow-ack-ms",
                "250",
                "--output",
                "json",
            ]
        )

        payload = json.loads(stdout)

        self.assertEqual(exit_code, 2)
        self.assertEqual(stderr, "")
        self.assertGreaterEqual(len(payload["anomalies"]), 1)
        self.assertEqual(payload["metrics"]["rejected_count"], 3)

    def test_analyze_missing_file_returns_input_error(self) -> None:
        exit_code, stdout, stderr = _run_cli(
            ["analyze", "--file", str(ROOT / "sample_logs" / "missing.log")]
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Log file not found", stderr)

    def test_analyze_symbol_filter_limits_lifecycles(self) -> None:
        exit_code, stdout, _stderr = _run_cli(
            [
                "analyze",
                "--file",
                str(ROOT / "sample_logs" / "orders_basic.log"),
                "--symbol",
                "ES",
                "--output",
                "json",
            ]
        )

        payload = json.loads(stdout)

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["metrics"]["total_orders"], 1)
        self.assertEqual(payload["metrics"]["counts_by_symbol"], {"ES": 1})

    def test_analyze_with_db_can_be_listed_by_runs_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "tradeops.db"

            analyze_exit, _stdout, analyze_stderr = _run_cli(
                [
                    "analyze",
                    "--file",
                    str(ROOT / "sample_logs" / "orders_basic.log"),
                    "--db",
                    str(db_path),
                ]
            )
            runs_exit, runs_stdout, runs_stderr = _run_cli(
                ["runs", "--db", str(db_path), "--output", "json"]
            )

            runs_payload = json.loads(runs_stdout)

            self.assertEqual(analyze_exit, 0)
            self.assertIn("stored analysis run #1", analyze_stderr)
            self.assertEqual(runs_exit, 0)
            self.assertEqual(runs_stderr, "")
            self.assertEqual(runs_payload[0]["total_orders"], 3)

    def test_analyze_rejects_non_positive_slow_ack_threshold(self) -> None:
        exit_code, stdout, stderr = _run_cli(
            [
                "analyze",
                "--file",
                str(ROOT / "sample_logs" / "orders_basic.log"),
                "--slow-ack-ms",
                "0",
            ]
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("--slow-ack-ms must be greater than zero", stderr)

    def test_runs_rejects_non_positive_limit(self) -> None:
        exit_code, stdout, stderr = _run_cli(["runs", "--db", "tradeops.db", "--limit", "0"])

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("--limit must be greater than zero", stderr)


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(argv)
    return exit_code, stdout.getvalue(), stderr.getvalue()
