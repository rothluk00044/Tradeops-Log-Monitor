# TradeOps Log Monitor

Local Python CLI for parsing simulated order-event logs, reconstructing order lifecycles, and flagging rejects, latency issues, malformed input, and abnormal trading workflow patterns.

## Overview

TradeOps Log Monitor is a local-first command-line tool for analyzing order event streams. It reads log files from disk, groups events by order ID, reconstructs each order's lifecycle, calculates operational metrics, and highlights anomalies that would matter during production-style support or troubleshooting.

The project is intentionally lightweight:

- Runs fully locally
- Uses Python standard library runtime code
- Requires no cloud services, APIs, or external systems
- Supports plain-text, JSON-lines, and CSV-style log inputs
- Optionally stores analysis history in a local SQLite database

## What It Detects

The analyzer is designed to make event-stream problems visible instead of silently ignoring them.

It can detect:

- Slow ACKs over a configurable threshold
- Orders missing ACK events
- Fills before ACKs
- Duplicate lifecycle events
- Unknown event types
- Malformed log lines
- Missing order IDs
- Reject spikes by reason
- Symbol-specific activity spikes

These findings help distinguish normal order flow from patterns that may indicate latency, bad sequencing, rejected workflow paths, parser issues, or unexpected upstream behavior.

## Example Log Input

```text
2026-05-19T09:30:01.125 ORDER_NEW id=ORD123 symbol=ES side=BUY qty=2
2026-05-19T09:30:01.220 ORDER_ACK id=ORD123
2026-05-19T09:30:02.000 ORDER_FILL id=ORD123 qty=2 price=5280.25
2026-05-19T09:31:15.100 ORDER_NEW id=ORD124 symbol=NQ side=SELL qty=1
2026-05-19T09:31:15.900 ORDER_REJECT id=ORD124 reason=RISK_LIMIT
```

## Installation

Python 3.11 or newer is recommended.

Create and activate a virtual environment:

```bash
python -m venv .venv
```

On Windows PowerShell:

```bash
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

Install the project and dashboard dependencies:

```bash
python -m pip install -e .
```

## Quick Start

From the repository root:

```bash
python -m tradeops_monitor analyze --file sample_logs/orders_basic.log
```

Show per-order lifecycle details:

```bash
python -m tradeops_monitor analyze --file sample_logs/orders_basic.log --show-orders
```

Analyze a file with a stricter ACK latency threshold:

```bash
python -m tradeops_monitor analyze --file sample_logs/orders_anomalies.log --slow-ack-ms 250
```

Emit JSON for automation:

```bash
python -m tradeops_monitor analyze --file sample_logs/orders_anomalies.log --slow-ack-ms 250 --output json
```

Filter by symbol:

```bash
python -m tradeops_monitor analyze --file sample_logs/orders_basic.log --symbol ES --show-orders
```

## Dashboard

The dashboard is currently in active development. It is usable for local exploration, sample-log analysis, CLI-engine validation, and UI iteration, but it should be treated as a development preview rather than a fully finished application.

Launch the local dashboard:

```bash
streamlit run dashboard.py
```

You can also launch it as a module:

```bash
python -m tradeops_monitor.dashboard
```

The dashboard keeps the CLI engine intact and reuses the same parser, lifecycle reconstruction, metrics, anomaly detection, and SQLite storage code.

## Sample Log Scenarios

The repository includes multiple local sample logs for testing different operating conditions:

- `orders_basic.log`: small clean lifecycle sample.
- `orders_anomalies.log`: mixed malformed lines, unknown events, rejects, slow ACKs, and sequencing issues.
- `orders_large.log`: larger mixed order flow.
- `orders_normal_day.log`: mostly normal fills, ACKs, and one cancellation.
- `orders_high_rejects.log`: elevated rejects with repeated reject reasons.
- `orders_latency_spike.log`: multiple slow ACKs across symbols.
- `orders_malformed.log`: malformed fields, unknown events, missing IDs, and invalid numeric values.
- `orders_mixed_anomalies.log`: combined slow ACK, reject spike, duplicate lifecycle event, unknown event, malformed row, and fill-before-ACK examples.

These files are intentionally small enough to inspect by hand while still exercising the main parser, lifecycle, metrics, anomaly, dashboard, and report-export paths.

## SQLite Storage

Analysis runs can be stored in a local SQLite database:

```bash
python -m tradeops_monitor analyze --file sample_logs/orders_basic.log --db tradeops.db
```

List recent stored runs:

```bash
python -m tradeops_monitor runs --db tradeops.db
```

List runs as JSON:

```bash
python -m tradeops_monitor runs --db tradeops.db --output json
```

## CLI Options

### Analyze Command

```bash
python -m tradeops_monitor analyze --file sample_logs/orders_basic.log [options]
```

Options:

- `--file`: path to a local log file
- `--format`: input format, one of `plain`, `json`, or `csv`
- `--slow-ack-ms`: ACK latency threshold in milliseconds
- `--output`: output format, either `text` or `json`
- `--symbol`: only analyze orders for one symbol
- `--show-orders`: include per-order lifecycle details
- `--db`: optional local SQLite database path

### Runs Command

```bash
python -m tradeops_monitor runs --db tradeops.db [options]
```

Options:

- `--db`: local SQLite database path
- `--limit`: maximum number of stored runs to display
- `--output`: output format, either `text` or `json`

## Exit Codes

- `0`: analysis completed normally
- `1`: input or CLI error, such as a missing file
- `2`: analysis completed, but critical anomalies were found

Exit code `2` is intentional. It means the tool successfully parsed enough data to report a serious issue, such as a fill before ACK or critical malformed input.

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

## Project Structure

```text
tradeops-log-monitor/
  README.md
  pyproject.toml
  sample_logs/
    orders_basic.log
    orders_anomalies.log
    orders_high_rejects.log
    orders_latency_spike.log
    orders_large.log
    orders_malformed.log
    orders_mixed_anomalies.log
    orders_normal_day.log
  tradeops_monitor/
    __init__.py
    __main__.py
    cli.py
    dashboard.py
    models.py
    parser.py
    lifecycle.py
    metrics.py
    anomalies.py
    reporting.py
    services.py
    storage.py
    output.py
  dashboard.py
  tests/
    test_parser.py
    test_lifecycle.py
    test_metrics.py
    test_anomalies.py
    test_cli.py
    test_reporting.py
    test_services.py
    test_storage.py
```

## How The Pipeline Works

1. `parser.py` reads local log lines and converts them into structured order events.
2. `lifecycle.py` groups events by order ID and determines each order's final status.
3. `metrics.py` calculates counts, latency values, reject summaries, and symbol/side totals.
4. `anomalies.py` flags suspicious or invalid workflow patterns.
5. `output.py` formats the result as readable text or JSON.
6. `storage.py` optionally persists runs, orders, events, and anomalies to SQLite.
7. `reporting.py` creates incident summaries, severity scoring, dashboard table rows, and report exports.
8. `dashboard.py` presents the local Streamlit interface without duplicating analysis logic.

## Testing

Run the full test suite:

```bash
python -m unittest discover -s tests
```

Run a focused test module:

```bash
python -m unittest tests.test_parser
python -m unittest tests.test_lifecycle
python -m unittest tests.test_anomalies
```
