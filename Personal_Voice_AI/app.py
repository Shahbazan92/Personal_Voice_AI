"""Personal Voice AI Studio — Streamlit entry point.  Run with:  streamlit run app.py"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

import config

st.set_page_config(page_title=config.APP_NAME, page_icon=config.APP_ICON, layout="wide",
                   initial_sidebar_state="expanded")

from ui import (about_page, components, dashboard_page, generate_page, library_page,  # noqa: E402
                profiles_page, settings_page)
from ui.services import get_services, load_settings  # noqa: E402

PAGES = {
    "🏠 Dashboard": dashboard_page,
    "🎤 Voice Profiles": profiles_page,
    "🗣️ Generate Speech": generate_page,
    "📚 Audio Library": library_page,
    "⚙️ Settings": settings_page,
    "ℹ️ About": about_page,
}


def main() -> None:
    components.inject_css()
    services = get_services()
    settings = load_settings()

    with st.sidebar:
        logo = config.BASE_DIR / "assets" / "logo.png"
        if logo.is_file():
            st.image(str(logo), width=72)
        st.markdown(f"### {config.APP_NAME}")
        st.radio("Navigation", list(PAGES), key="nav", label_visibility="collapsed")
        st.divider()
        st.caption("Theme: use the ⋮ menu → Settings → Theme (light / dark).")
        st.caption(f"v{config.APP_VERSION} · local-first")

    PAGES[st.session_state["nav"]].render(services, settings)


main()
