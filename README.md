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

## Development

Run tests:

```bash
python -m unittest discover -s tests
```

More usage examples and sample output will be added as the CLI features land.
