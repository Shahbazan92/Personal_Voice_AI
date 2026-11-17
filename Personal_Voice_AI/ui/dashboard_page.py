from __future__ import annotations

import streamlit as st

from core import model_manager
from core.voice_cloner import ENGINES, resolve_engine_name
from ui import components
from ui.services import Services, get_engine, remote_credentials
from utils.helpers import format_duration, format_timestamp


def render(services: Services, settings) -> None:
    components.hero("Dashboard", "Your personal voice, in many languages.")
    url, _ = remote_credentials(settings)
    engine_name = resolve_engine_name(settings.engine, url)
    engine = get_engine(settings, services)
    ready, reason = engine.is_available()

    c = st.columns(4)
    c[0].metric("Voice profiles", services.db.count_profiles())
    c[1].metric("Generated files", services.db.count_generations())
    c[2].metric("Supported languages", services.languages.count())
    c[3].metric("Selected model", ENGINES[engine_name].label.split(" (")[0])

    status = "✅ Loaded and ready" if engine.is_loaded else ("🟡 Available — loads on first generation" if ready else f"🔴 {reason}")
    st.caption(f"Engine status: {status}")
    if engine_name == "xtts_v2" and ready and not model_manager.is_model_downloaded():
        st.info("The XTTS-v2 model has not been downloaded yet. Open **Generate Speech** to download it (≈1.8 GB, one time).")

    st.button("⚡ Quick Generate Speech", type="primary", on_click=components.go_to, args=("🗣️ Generate Speech",))

    st.subheader("Recently generated")
    recent = services.db.list_generations(limit=5)
    if not recent:
        st.write("Nothing yet. Create a voice profile, then generate your first speech.")
    for rec in recent:
        with st.container(border=True):
            st.write(f"**{rec['profile_name'] or 'Deleted profile'}** · {services.languages.name_for(rec['language'])} · "
                     f"{format_duration(rec['duration_sec'])} · {format_timestamp(rec['created_at'])}")
            st.caption(rec["input_text"][:140] + ("…" if len(rec["input_text"]) > 140 else ""))
            if services.storage.exists(rec["output_audio_path"]):
                st.audio(str(services.storage.local_path(rec["output_audio_path"])))
            else:
                st.caption("Audio file no longer available (storage may be temporary on this host).")
