from __future__ import annotations

import streamlit as st

import config
from core import audio_processor, model_manager
from core.voice_cloner import ENGINES
from ui import components
from ui.services import Services, remote_credentials


def render(services: Services, settings) -> None:
    components.hero("Settings", "Model, hardware, output and quality.")
    status = model_manager.get_status()

    with st.form("settings_form"):
        st.subheader("AI model")
        engine_options = ["auto", *ENGINES.keys()]
        settings.engine = st.selectbox(
            "Engine", engine_options, index=engine_options.index(settings.engine) if settings.engine in engine_options else 0,
            format_func=lambda k: "Automatic (local XTTS-v2, else remote)" if k == "auto" else ENGINES[k].label)
        device_options = ["auto", "cpu", "cuda"]
        settings.device = st.selectbox("Processing device", device_options, index=device_options.index(settings.device),
                                       help="Changes apply after the engine is reloaded (restart the app).")
        st.caption("CUDA GPU detected." if status.cuda_available else "No CUDA GPU detected — the model will run on CPU (slow).")

        st.subheader("Output")
        settings.output_format = st.radio("Stored audio format", ["wav", "mp3"], horizontal=True,
                                          index=["wav", "mp3"].index(settings.output_format))
        settings.mp3_bitrate = st.selectbox("MP3 bitrate", ["128k", "192k", "256k", "320k"],
                                            index=["128k", "192k", "256k", "320k"].index(settings.mp3_bitrate)
                                            if settings.mp3_bitrate in ("128k", "192k", "256k", "320k") else 1)
        if not audio_processor.ffmpeg_available():
            st.warning("FFmpeg was not found: MP3 output is unavailable (WAV is used instead).")
        st.text_input("Output folder (set with the PVAI_DATA_DIR environment variable)",
                      value=str(config.OUTPUTS_DIR), disabled=True)

        st.subheader("Audio & quality")
        settings.noise_reduction_default = st.checkbox("Reduce noise by default when adding recordings",
                                                       value=settings.noise_reduction_default)
        settings.temperature = st.slider("Default temperature", 0.1, 1.2, float(settings.temperature), 0.05)
        settings.speed = st.slider("Default speed", 0.7, 1.3, float(settings.speed), 0.05)
        settings.repetition_penalty = st.slider("Default repetition penalty", 1.0, 10.0, float(settings.repetition_penalty), 0.5)
        settings.top_p = st.slider("Top-p", 0.1, 1.0, float(settings.top_p), 0.05)
        settings.top_k = st.slider("Top-k", 1, 100, int(settings.top_k))

        st.subheader("Remote GPU server (optional)")
        settings.remote_url = st.text_input("Server URL", value=settings.remote_url, placeholder="https://gpu.example.com")
        key_in = st.text_input("API key (kept in this browser session only, never written to disk)", type="password")
        saved = st.form_submit_button("💾 Save settings", type="primary")

    if saved:
        if key_in:
            st.session_state["remote_api_key"] = key_in
        settings.save(config.SETTINGS_PATH)
        st.success("Settings saved. If you changed the engine/device, restart the app (or clear the cache) to reload it.")

    st.subheader("System")
    url, key = remote_credentials(settings)
    st.write(f"- Version: **{config.APP_VERSION}**\n- Python packages for local XTTS-v2: "
             f"{'✅ installed' if status.deps_installed else '❌ missing: ' + ', '.join(status.missing)}\n"
             f"- Model downloaded: {'✅' if status.model_downloaded else '❌ not yet'}\n"
             f"- Remote server configured: {'✅' if url else '—'} · API key present: {'✅' if key else '—'}\n"
             f"- RAM: {f'{status.available_ram_gb:.1f} GB free of {status.total_ram_gb:.1f} GB' if status.total_ram_gb else 'unknown'}\n"
             f"- Data folder: `{config.DATA_DIR}`")
    if st.button("♻️ Clear cached engine (reload model)"):
        st.cache_resource.clear()
        st.rerun()
