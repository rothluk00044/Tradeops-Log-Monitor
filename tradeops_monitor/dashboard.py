"""Local Streamlit dashboard for TradeOps Log Monitor."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from .models import AnalysisReport
from .reporting import (
    ANOMALY_EXPLANATIONS,
    anomaly_rows,
    assess_operational_severity,
    build_incident_summary,
    build_json_export,
    build_markdown_report,
    event_timeline_rows,
    latency_percentiles,
    latency_rows,
    order_rows,
    report_filename,
    save_report_exports,
    symbol_summary_rows,
    unknown_event_count,
)
from .services import build_analysis_report, build_analysis_report_from_lines
from .storage import list_recent_runs, store_report


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_LOG_DIR = ROOT / "sample_logs"


def main() -> None:
    st.set_page_config(
        page_title="TradeOps Log Monitor",
        page_icon=None,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _apply_styles()
    st.title("TradeOps Log Monitor")
    st.caption("Local order-event diagnostics for lifecycle, latency, rejects, and workflow anomalies.")

    report = _sidebar_controls()
    if report is None:
        st.info("Choose a sample log or upload a local log file, then run analysis.")
        return

    _render_export_actions(report)
    tabs = st.tabs(["Overview", "Orders", "Anomalies", "Latency", "Symbols", "Run History", "Replay", "About"])
    with tabs[0]:
        _render_overview(report)
    with tabs[1]:
        _render_orders(report)
    with tabs[2]:
        _render_anomalies(report)
    with tabs[3]:
        _render_latency(report)
    with tabs[4]:
        _render_symbols(report)
    with tabs[5]:
        _render_run_history_controls(report)
    with tabs[6]:
        _render_replay(report)
    with tabs[7]:
        _render_about()


def _sidebar_controls() -> AnalysisReport | None:
    st.sidebar.header("Analysis Controls")
    sample_paths = _sample_log_paths()
    source_mode = st.sidebar.radio("Source", ["Sample log", "Upload file"], horizontal=True)
    input_format = st.sidebar.selectbox("Input format", ["plain", "json", "csv"], index=0)
    slow_ack_ms = st.sidebar.slider("Slow ACK threshold (ms)", min_value=50, max_value=2000, value=500, step=50)
    symbol_filter = st.sidebar.text_input("Symbol filter", placeholder="Optional, e.g. ES").strip() or None

    uploaded_file = None
    selected_sample = sample_paths[0] if sample_paths else None
    if source_mode == "Sample log":
        labels = [path.name for path in sample_paths]
        selected_label = st.sidebar.selectbox("Sample log", labels, index=0)
        selected_sample = SAMPLE_LOG_DIR / selected_label
    else:
        uploaded_file = st.sidebar.file_uploader("Upload local log", type=["log", "txt", "json", "csv"])

    run_analysis = st.sidebar.button("Run analysis", type="primary", use_container_width=True)
    if "dashboard_report" not in st.session_state and selected_sample and source_mode == "Sample log":
        run_analysis = True

    if not run_analysis:
        return st.session_state.get("dashboard_report")

    try:
        if source_mode == "Upload file":
            if uploaded_file is None:
                st.sidebar.error("Upload a file before running analysis.")
                return st.session_state.get("dashboard_report")
            text = uploaded_file.getvalue().decode("utf-8")
            report = build_analysis_report_from_lines(
                lines=text.splitlines(),
                source_file=uploaded_file.name,
                input_format=input_format,
                slow_ack_ms=slow_ack_ms,
                symbol=symbol_filter,
            )
        else:
            if selected_sample is None:
                st.sidebar.error("No sample logs were found.")
                return None
            report = build_analysis_report(
                file_path=selected_sample,
                input_format=input_format,
                slow_ack_ms=slow_ack_ms,
                symbol=symbol_filter,
            )
    except Exception as exc:  # Streamlit should show local input errors clearly.
        st.sidebar.error(str(exc))
        return st.session_state.get("dashboard_report")

    st.session_state["dashboard_report"] = report
    return report


def _render_overview(report: AnalysisReport) -> None:
    severity = assess_operational_severity(report)
    metrics = report.metrics
    st.subheader("Overview")
    st.markdown(f"<div class='severity severity-{severity.level.lower()}'>Severity: {severity.level}</div>", unsafe_allow_html=True)
    st.write(build_incident_summary(report))

    first_row = st.columns(4)
    first_row[0].metric("Total Orders", metrics.total_orders)
    first_row[1].metric("Filled", metrics.filled_count)
    first_row[2].metric("Rejected", metrics.rejected_count)
    first_row[3].metric("Canceled", metrics.canceled_count)

    second_row = st.columns(4)
    second_row[0].metric("Open / Incomplete", metrics.open_incomplete_count)
    second_row[1].metric("Avg ACK Latency", _format_ms(metrics.average_ack_latency_ms))
    second_row[2].metric("Slow ACKs", metrics.slow_ack_count)
    second_row[3].metric("Malformed Lines", report.parse_result.malformed_count)

    third_row = st.columns(2)
    third_row[0].metric("Unknown Events", unknown_event_count(report))
    third_row[1].metric("Anomalies", len(report.anomalies))

    with st.expander("Severity rationale", expanded=False):
        for reason in severity.reasons:
            st.write(f"- {reason}")


def _render_export_actions(report: AnalysisReport) -> None:
    left, middle, right = st.columns([1, 1, 1])
    with left:
        st.download_button(
            "Download Markdown report",
            data=build_markdown_report(report),
            file_name=report_filename(report.source_file, "md"),
            mime="text/markdown",
        )
    with middle:
        st.download_button(
            "Download JSON report",
            data=build_json_export(report),
            file_name=report_filename(report.source_file, "json"),
            mime="application/json",
        )
    with right:
        if st.button("Save report files"):
            markdown_path, json_path = save_report_exports(report)
            st.success(f"Saved {markdown_path} and {json_path}.")


def _render_run_history_controls(report: AnalysisReport) -> None:
    st.subheader("Run History")
    db_path = st.text_input("SQLite database path", value="tradeops.db")
    if st.button("Save current run", use_container_width=False):
        run_id = store_report(db_path, report)
        st.success(f"Saved analysis run #{run_id} to {db_path}.")

    try:
        runs = list_recent_runs(db_path, limit=25)
    except Exception as exc:  # Keep database path issues visible in the UI.
        st.error(str(exc))
        return

    if not runs:
        st.info("No stored runs found for this database path.")
        return

    run_df = pd.DataFrame([run.to_dict() for run in runs])
    st.dataframe(run_df, use_container_width=True, hide_index=True)


def _render_orders(report: AnalysisReport) -> None:
    st.subheader("Orders")
    rows = order_rows(report)
    if not rows:
        st.info("No orders matched the current analysis filters.")
        return

    df = pd.DataFrame(rows)
    filters = st.columns([1.4, 1, 1, 1])
    order_query = filters[0].text_input("Search order ID", placeholder="ORD123").strip().upper()
    symbol_options = sorted(df["symbol"].dropna().unique())
    side_options = sorted(df["side"].dropna().unique())
    status_options = sorted(df["status"].dropna().unique())
    selected_symbols = filters[1].multiselect("Symbol", symbol_options)
    selected_sides = filters[2].multiselect("Side", side_options)
    selected_statuses = filters[3].multiselect("Status", status_options)

    filtered = df
    if order_query:
        filtered = filtered[filtered["order_id"].str.upper().str.contains(order_query, na=False)]
    if selected_symbols:
        filtered = filtered[filtered["symbol"].isin(selected_symbols)]
    if selected_sides:
        filtered = filtered[filtered["side"].isin(selected_sides)]
    if selected_statuses:
        filtered = filtered[filtered["status"].isin(selected_statuses)]

    st.dataframe(
        filtered.style.map(_status_cell_style, subset=["status"]),
        use_container_width=True,
        hide_index=True,
    )

    selected_order = st.selectbox("Inspect event history", [""] + sorted(report.lifecycles))
    if selected_order:
        lifecycle = report.lifecycles[selected_order]
        event_df = pd.DataFrame(
            [
                {
                    "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                    "event_type": event.raw_event_type,
                    "qty": event.qty,
                    "price": event.price,
                    "reason": event.reason,
                    "line_number": event.line_number,
                    "raw_line": event.raw_line,
                }
                for event in lifecycle.events
            ]
        )
        st.markdown(f"**{selected_order} final status:** `{lifecycle.status.value}`")
        st.dataframe(event_df, use_container_width=True, hide_index=True)


def _render_anomalies(report: AnalysisReport) -> None:
    st.subheader("Anomalies")
    rows = anomaly_rows(report)
    if not rows:
        st.success("No anomalies detected for the current analysis.")
        return

    df = pd.DataFrame(rows)
    filters = st.columns(3)
    selected_severities = filters[0].multiselect("Severity", sorted(df["severity"].unique()))
    selected_types = filters[1].multiselect("Type", sorted(df["type"].unique()))
    order_query = filters[2].text_input("Order ID", placeholder="Optional").strip().upper()

    filtered = df
    if selected_severities:
        filtered = filtered[filtered["severity"].isin(selected_severities)]
    if selected_types:
        filtered = filtered[filtered["type"].isin(selected_types)]
    if order_query:
        filtered = filtered[filtered["order_id"].fillna("").str.upper().str.contains(order_query)]

    st.dataframe(
        filtered.style.map(_severity_cell_style, subset=["severity"]),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Anomaly type guide", expanded=False):
        for anomaly_type, explanation in ANOMALY_EXPLANATIONS.items():
            st.markdown(f"**{anomaly_type}:** {explanation}")


def _render_latency(report: AnalysisReport) -> None:
    st.subheader("Latency")
    rows = latency_rows(report)
    if not rows:
        st.info("No ACK latency values are available.")
        return

    df = pd.DataFrame(rows)
    percentiles = latency_percentiles(report)
    cols = st.columns(4)
    cols[0].metric("Threshold", f"{report.slow_ack_ms}ms")
    cols[1].metric("p50", _format_ms(percentiles["p50"]))
    cols[2].metric("p95", _format_ms(percentiles["p95"]))
    cols[3].metric("Max", _format_ms(percentiles["max"]))

    chart_df = df.sort_values("ack_latency_ms").set_index("order_id")[["ack_latency_ms"]]
    st.bar_chart(chart_df, use_container_width=True)
    st.markdown("**Top slowest orders**")
    st.dataframe(df.head(10), use_container_width=True, hide_index=True)


def _render_symbols(report: AnalysisReport) -> None:
    st.subheader("Symbols")
    rows = symbol_summary_rows(report)
    if not rows:
        st.info("No symbol-level data is available.")
        return

    df = pd.DataFrame(rows)
    chart_df = df.set_index("symbol")
    left, right = st.columns(2)
    left.markdown("**Order count by symbol**")
    left.bar_chart(chart_df[["orders"]], use_container_width=True)
    right.markdown("**Reject rate by symbol**")
    right.bar_chart(chart_df[["reject_rate"]], use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_replay(report: AnalysisReport) -> None:
    st.subheader("Replay Mode")
    rows = event_timeline_rows(report)
    if not rows:
        st.info("No events are available to replay.")
        return

    max_events = len(rows)
    visible_count = st.slider("Timeline position", min_value=1, max_value=max_events, value=max_events)
    visible = pd.DataFrame(rows[:visible_count])
    st.caption("Replay mode shows the event stream in chronological order up to the selected point.")
    st.dataframe(visible, use_container_width=True, hide_index=True)

    latest = rows[visible_count - 1]
    st.markdown(
        f"Latest event: `{latest['event_type']}` "
        f"for order `{latest['order_id'] or 'UNKNOWN'}` "
        f"at `{latest['timestamp'] or 'UNKNOWN'}`"
    )


def _render_about() -> None:
    st.subheader("About")
    st.write(
        "TradeOps Log Monitor is a local-first dashboard for parsing simulated order-event logs, "
        "reconstructing order lifecycles, calculating latency and reject metrics, and surfacing workflow anomalies."
    )
    st.code(
        "2026-05-19T09:30:01.125 ORDER_NEW id=ORD123 symbol=ES side=BUY qty=2\n"
        "2026-05-19T09:30:01.220 ORDER_ACK id=ORD123\n"
        "2026-05-19T09:30:02.000 ORDER_FILL id=ORD123 qty=2 price=5280.25",
        language="text",
    )
    st.write(
        "All analysis runs locally. SQLite persistence is optional and writes only to the database path you choose."
    )


def _sample_log_paths() -> list[Path]:
    if not SAMPLE_LOG_DIR.exists():
        return []
    return sorted(SAMPLE_LOG_DIR.glob("*.log"))


def _apply_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: #0f172a;
            color: #e5e7eb;
        }
        [data-testid="stSidebar"] {
            background: #111827;
        }
        .severity {
            border-radius: 6px;
            display: inline-block;
            font-weight: 700;
            margin: 0.25rem 0 1rem 0;
            padding: 0.4rem 0.7rem;
        }
        .severity-low {
            background: rgba(34, 197, 94, 0.16);
            border: 1px solid rgba(34, 197, 94, 0.55);
            color: #86efac;
        }
        .severity-medium {
            background: rgba(245, 158, 11, 0.16);
            border: 1px solid rgba(245, 158, 11, 0.55);
            color: #fcd34d;
        }
        .severity-high {
            background: rgba(239, 68, 68, 0.18);
            border: 1px solid rgba(239, 68, 68, 0.6);
            color: #fca5a5;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _format_ms(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}ms"


def _status_cell_style(value: str) -> str:
    colors = {
        "FILLED": "background-color: #14532d; color: #bbf7d0;",
        "REJECTED": "background-color: #7f1d1d; color: #fecaca;",
        "CANCELED": "background-color: #78350f; color: #fde68a;",
        "PARTIALLY_FILLED": "background-color: #1e3a8a; color: #bfdbfe;",
        "ACKED": "background-color: #164e63; color: #a5f3fc;",
        "NEW_ONLY": "background-color: #3f3f46; color: #e4e4e7;",
        "INCOMPLETE": "background-color: #581c87; color: #e9d5ff;",
        "UNKNOWN": "background-color: #3f3f46; color: #e4e4e7;",
    }
    return colors.get(value, "")


def _severity_cell_style(value: str) -> str:
    colors = {
        "INFO": "background-color: #164e63; color: #a5f3fc;",
        "WARNING": "background-color: #78350f; color: #fde68a;",
        "CRITICAL": "background-color: #7f1d1d; color: #fecaca;",
    }
    return colors.get(value, "")


if __name__ == "__main__":
    main()
