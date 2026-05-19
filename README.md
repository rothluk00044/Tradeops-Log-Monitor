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

## Planned CLI

```bash
python -m tradeops_monitor analyze --file sample_logs/orders_basic.log
python -m tradeops_monitor analyze --file sample_logs/orders_anomalies.log --slow-ack-ms 250 --output json
python -m tradeops_monitor analyze --file sample_logs/orders_basic.log --db tradeops.db
python -m tradeops_monitor runs --db tradeops.db
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

## Development

Run tests:

```bash
python -m unittest
```

More usage examples and sample output will be added as the CLI features land.
