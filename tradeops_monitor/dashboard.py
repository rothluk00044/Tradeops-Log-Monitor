"""Local Streamlit dashboard for TradeOps Log Monitor."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from .models import AnalysisReport
from .reporting import (
    assess_operational_severity,
    build_incident_summary,
    build_json_export,
    build_markdown_report,
    report_filename,
    unknown_event_count,
)
from .services import build_analysis_report, build_analysis_report_from_lines
from .storage import store_report


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
        st.info("Order lifecycle table will appear here.")
    with tabs[2]:
        st.info("Anomaly review will appear here.")
    with tabs[3]:
        st.info("Latency distribution will appear here.")
    with tabs[4]:
        st.info("Symbol activity will appear here.")
    with tabs[5]:
        _render_run_history_controls(report)
    with tabs[6]:
        st.info("Replay mode will appear here.")
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
    left, right = st.columns([1, 1])
    with left:
        st.download_button(
            "Download Markdown report",
            data=build_markdown_report(report),
            file_name=report_filename(report.source_file, "md"),
            mime="text/markdown",
        )
    with right:
        st.download_button(
            "Download JSON report",
            data=build_json_export(report),
            file_name=report_filename(report.source_file, "json"),
            mime="application/json",
        )


def _render_run_history_controls(report: AnalysisReport) -> None:
    st.subheader("Run History")
    db_path = st.text_input("SQLite database path", value="tradeops.db")
    if st.button("Save current run", use_container_width=False):
        run_id = store_report(db_path, report)
        st.success(f"Saved analysis run #{run_id} to {db_path}.")
    st.caption("Recent run table is added in the next dashboard layer.")


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


if __name__ == "__main__":
    main()
