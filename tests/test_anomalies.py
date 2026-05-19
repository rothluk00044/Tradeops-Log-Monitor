"""Anomaly detection tests."""

from __future__ import annotations

import unittest

from tradeops_monitor.anomalies import detect_anomalies, has_critical_anomalies
from tradeops_monitor.lifecycle import reconstruct_lifecycles
from tradeops_monitor.models import AnomalyType
from tradeops_monitor.parser import parse_lines


class AnomalyTests(unittest.TestCase):
    def test_detects_slow_ack_and_missing_ack(self) -> None:
        result = parse_lines(
            [
                "2026-05-19T09:30:00.000 ORDER_NEW id=ORD1 symbol=ES side=BUY qty=1",
                "2026-05-19T09:30:00.600 ORDER_ACK id=ORD1",
                "2026-05-19T09:31:00.000 ORDER_NEW id=ORD2 symbol=NQ side=SELL qty=1",
            ]
        )
        lifecycles = reconstruct_lifecycles(result.events)

        anomalies = detect_anomalies(result, lifecycles.values(), slow_ack_ms=250)
        anomaly_types = {anomaly.anomaly_type for anomaly in anomalies}

        self.assertIn(AnomalyType.SLOW_ACK, anomaly_types)
        self.assertIn(AnomalyType.MISSING_ACK, anomaly_types)

    def test_detects_fill_before_ack_as_critical(self) -> None:
        result = parse_lines(
            [
                "2026-05-19T09:30:00.000 ORDER_NEW id=ORD1 symbol=ES side=BUY qty=1",
                "2026-05-19T09:30:00.100 ORDER_FILL id=ORD1 qty=1 price=5280.00",
                "2026-05-19T09:30:00.200 ORDER_ACK id=ORD1",
            ]
        )
        anomalies = detect_anomalies(result, reconstruct_lifecycles(result.events).values())

        self.assertIn(AnomalyType.FILL_BEFORE_ACK, {anomaly.anomaly_type for anomaly in anomalies})
        self.assertTrue(has_critical_anomalies(anomalies))

    def test_detects_duplicate_lifecycle_events(self) -> None:
        result = parse_lines(
            [
                "2026-05-19T09:30:00.000 ORDER_NEW id=ORD1 symbol=ES side=BUY qty=1",
                "2026-05-19T09:30:00.050 ORDER_NEW id=ORD1 symbol=ES side=BUY qty=1",
                "2026-05-19T09:30:00.100 ORDER_ACK id=ORD1",
            ]
        )
        anomalies = detect_anomalies(result, reconstruct_lifecycles(result.events).values())

        self.assertIn(AnomalyType.DUPLICATE_LIFECYCLE_EVENT, {anomaly.anomaly_type for anomaly in anomalies})

    def test_reports_parse_issues_and_unknown_events(self) -> None:
        result = parse_lines(
            [
                "not enough",
                "2026-05-19T09:30:00.000 ORDER_HELD id=ORD1 symbol=ES",
            ]
        )
        anomalies = detect_anomalies(result, reconstruct_lifecycles(result.events).values())
        anomaly_types = [anomaly.anomaly_type for anomaly in anomalies]

        self.assertIn(AnomalyType.PARSE_ISSUE, anomaly_types)
        self.assertIn(AnomalyType.UNKNOWN_EVENT_TYPE, anomaly_types)

    def test_detects_reject_spikes_by_reason(self) -> None:
        result = parse_lines(
            [
                "2026-05-19T09:30:00.000 ORDER_NEW id=ORD1 symbol=NQ side=SELL qty=1",
                "2026-05-19T09:30:00.100 ORDER_REJECT id=ORD1 reason=RISK_LIMIT",
                "2026-05-19T09:31:00.000 ORDER_NEW id=ORD2 symbol=NQ side=SELL qty=1",
                "2026-05-19T09:31:00.100 ORDER_REJECT id=ORD2 reason=RISK_LIMIT",
                "2026-05-19T09:32:00.000 ORDER_NEW id=ORD3 symbol=NQ side=SELL qty=1",
                "2026-05-19T09:32:00.100 ORDER_REJECT id=ORD3 reason=RISK_LIMIT",
            ]
        )
        anomalies = detect_anomalies(
            result,
            reconstruct_lifecycles(result.events).values(),
            reject_spike_threshold=3,
        )

        self.assertIn(AnomalyType.REJECT_SPIKE, {anomaly.anomaly_type for anomaly in anomalies})

    def test_detects_symbol_activity_spikes(self) -> None:
        result = parse_lines(
            [
                "2026-05-19T09:30:00.000 ORDER_NEW id=ORD1 symbol=ES side=BUY qty=1",
                "2026-05-19T09:30:01.000 ORDER_NEW id=ORD2 symbol=ES side=BUY qty=1",
                "2026-05-19T09:30:02.000 ORDER_NEW id=ORD3 symbol=ES side=BUY qty=1",
            ]
        )
        anomalies = detect_anomalies(
            result,
            reconstruct_lifecycles(result.events).values(),
            symbol_activity_threshold=3,
        )

        self.assertIn(AnomalyType.SYMBOL_ACTIVITY_SPIKE, {anomaly.anomaly_type for anomaly in anomalies})
