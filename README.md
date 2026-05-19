# TradeOps Log Monitor

Local Python CLI for parsing simulated order-event logs, reconstructing order lifecycles, and flagging rejects, latency issues, and abnormal trading workflow patterns.

## What It Does

TradeOps Log Monitor reads local order event logs, groups events by order ID, reconstructs each order lifecycle, calculates operational metrics, and reports anomalies useful during support-style troubleshooting.

The project is intentionally local-first:

- no external services
- no cloud dependencies
- no paid APIs
- standard-library runtime code
- standard-library `unittest` coverage

## Install

Python 3.11 or newer is recommended.

```bash
python -m pip install -e .
```

The CLI can also be run directly from the repository without installing:

```bash
python -m tradeops_monitor analyze --file sample_logs/orders_basic.log
```

## CLI Usage

```bash
python -m tradeops_monitor analyze --file sample_logs/orders_basic.log
python -m tradeops_monitor analyze --file sample_logs/orders_anomalies.log --slow-ack-ms 250 --output json
python -m tradeops_monitor analyze --file sample_logs/orders_basic.log --db tradeops.db
python -m tradeops_monitor runs --db tradeops.db
```

Useful options:

- `--format plain/json/csv`: choose the input parser.
- `--slow-ack-ms 250`: flag ACK latency above the threshold.
- `--output text/json`: choose human-readable or automation-friendly output.
- `--symbol ES`: analyze orders for a single symbol.
- `--show-orders`: include per-order lifecycle details.
- `--db tradeops.db`: store the analysis in a local SQLite database.

Exit codes:

- `0`: analysis completed normally.
- `1`: input or CLI error, such as a missing file.
- `2`: analysis completed and critical anomalies were found.

## Sample Input

Plain-text logs use an ISO timestamp, event type, and key-value fields:

```text
2026-05-19T09:30:01.125 ORDER_NEW id=ORD123 symbol=ES side=BUY qty=2
2026-05-19T09:30:01.220 ORDER_ACK id=ORD123
2026-05-19T09:30:02.000 ORDER_FILL id=ORD123 qty=2 price=5280.25
2026-05-19T09:31:15.100 ORDER_NEW id=ORD124 symbol=NQ side=SELL qty=1
2026-05-19T09:31:15.900 ORDER_REJECT id=ORD124 reason=RISK_LIMIT
```

## Sample Output

```text
TradeOps Log Monitor Summary
============================
Source: sample_logs/orders_basic.log
Input format: plain
Parsed events: 10
Parse issues: 0

Metrics
- Total orders: 3
- Filled: 2
- Rejected: 0
- Canceled: 1
- Open/incomplete: 0
- Slow ACKs: 0
- Avg ACK latency: 211.7ms
- Min ACK latency: 95.0ms
- Max ACK latency: 390.0ms
- Reject reasons: none
- Counts by symbol: ES=1, NQ=1, YM=1
- Counts by side: BUY=2, SELL=1

Anomalies
- None
```

JSON output is available for automation:

```bash
python -m tradeops_monitor analyze --file sample_logs/orders_anomalies.log --output json
```

## Project Structure

```text
tradeops-log-monitor/
  README.md
  pyproject.toml
  sample_logs/
    orders_basic.log
    orders_anomalies.log
    orders_large.log
  tradeops_monitor/
    __init__.py
    __main__.py
    cli.py
    models.py
    parser.py
    lifecycle.py
    metrics.py
    anomalies.py
    storage.py
    output.py
  tests/
    test_parser.py
    test_lifecycle.py
    test_metrics.py
    test_anomalies.py
    test_cli.py
    test_storage.py
```

Module responsibilities:

- `parser.py`: parses plain-text, JSON-lines, and CSV order events.
- `lifecycle.py`: reconstructs order state from grouped events.
- `metrics.py`: calculates counts, latency, symbols, sides, and rejects.
- `anomalies.py`: flags slow ACKs, missing ACKs, fill-before-ACK, duplicates, unknown events, malformed lines, and activity spikes.
- `storage.py`: stores runs, orders, events, and anomalies in local SQLite.
- `output.py`: formats text and JSON reports.

## SQLite Storage

When `--db` is provided, the analysis is stored in a local SQLite database. The schema is intentionally simple:

- `runs`: one row per analysis execution.
- `orders`: reconstructed lifecycle summary per order.
- `events`: parsed event rows with original fields and raw line text.
- `anomalies`: detected anomalies with severity and details.

List recent stored runs:

```bash
python -m tradeops_monitor runs --db tradeops.db
python -m tradeops_monitor runs --db tradeops.db --output json
```

## Development

Run tests:

```bash
python -m unittest discover -s tests
```

Run a focused test module:

```bash
python -m unittest tests.test_parser
```

## Future Improvements

- Add configurable anomaly thresholds for reject and symbol spikes.
- Add richer CSV examples and fixtures.
- Add a compact per-symbol report view.
- Add export options for saved SQLite runs.
- Add support for additional simulated event types without changing existing parser contracts.
