"""Reusable UI pieces and global styling."""
from __future__ import annotations

import streamlit as st

import config

CSS = """
<style>
.block-container {padding-top: 2rem; max-width: 1150px;}
.pvai-hero {padding: 1.1rem 1.4rem; border-radius: 14px; margin-bottom: 1rem;
  background: linear-gradient(120deg, #6d5dfc 0%, #3b82f6 100%); color: #fff;}
.pvai-hero h1 {margin: 0; font-size: 1.7rem; color: #fff;}
.pvai-hero p {margin: .25rem 0 0 0; opacity: .92;}
div[data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.25); border-radius: 12px; padding: .7rem 1rem;}
</style>
"""

AI_NOTICE = (
    "Generated audio is AI-generated. Only clone your own voice or a voice you have explicit permission to use. "
    "Never use it to impersonate others, deceive, or commit fraud."
)


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="pvai-hero"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def go_to(page: str) -> None:
    """Button callback: switch the sidebar navigation to ``page``."""
    st.session_state["nav"] = page


def show_report(report) -> None:
    cols = st.columns(4)
    cols[0].metric("Duration", f"{report.duration:.1f} s")
    cols[1].metric("Quality", report.quality_label)
    cols[2].metric("Est. SNR", f"{report.snr_db:.0f} dB")
    cols[3].metric("Level", f"{report.rms_dbfs:.0f} dBFS")
    for msg in report.errors:
        st.error(msg)
    for msg in report.warnings:
        st.warning(msg)
