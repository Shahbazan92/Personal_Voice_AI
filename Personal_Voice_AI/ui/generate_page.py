from __future__ import annotations

import streamlit as st

import config
from core import model_manager
from core.audio_processor import AudioError
from core.engines.base import EngineError
from core.language_manager import UnsupportedLanguageError
from core.text_chunker import chunk_text
from ui import components
from ui.audio_widgets import audio_with_downloads
from ui.services import Services, apply_license_acceptance, get_engine, synthesis_settings
from utils.helpers import format_duration, slugify
from utils.validators import ValidationError


def _setup_gate(engine, settings, services) -> bool:
    """Show setup instructions / model download UI. Returns True when generation can proceed."""
    ready, reason = engine.is_available()
    if not ready:
        if engine.name == "xtts_v2":
            st.error(f"The local XTTS-v2 engine is not ready: {reason}")
            st.markdown("Install the model stack, then restart the app:")
            st.code("pip install -r requirements-xtts.txt", language="bash")
            st.caption("Prefer not to install it here? Configure a remote GPU server in **Settings**. See README → Deployment.")
        else:
            st.error(reason)
        return False

    if engine.name == "xtts_v2" and not engine.is_loaded:
        downloaded = model_manager.is_model_downloaded()
        avail, total = model_manager.memory_info()
        if total and total < 6 and engine.device_preference != "cuda":
            st.warning(f"This machine has about {total:.1f} GB RAM. XTTS-v2 on CPU typically needs 4–6 GB or more "
                       "and may fail to load. Consider the Remote GPU engine.")
        if not downloaded:
            st.info("First run: the XTTS-v2 model (≈1.8 GB) must be downloaded once. "
                    "It is stored in the models folder and re-used afterwards.")
            if not settings.coqui_license_accepted:
                st.markdown(f"XTTS-v2 is released under the [Coqui Public Model License]({config.XTTS_LICENSE_URL}) "
                            "(non-commercial use).")
                if st.checkbox("I have read and accept the Coqui Public Model License", key="lic_accept"):
                    settings.coqui_license_accepted = True
                    settings.save(config.SETTINGS_PATH)
                    st.rerun()
                return False
        apply_license_acceptance(settings)
        label = "⬇️ Download & load model" if not downloaded else "🔄 Load model now"
        if st.button(label):
            try:
                with st.status("Preparing XTTS-v2…", expanded=True) as status:
                    engine.load(lambda msg: status.write(msg))
                    status.update(label="Model ready", state="complete")
                st.rerun()
            except (model_manager.DependencyMissingError, model_manager.ModelLoadError,
                    model_manager.InsufficientMemoryError, EngineError) as exc:
                st.error(str(exc))
        st.caption("The model also loads automatically on your first generation.")
    return True


def render(services: Services, settings) -> None:
    components.hero("Generate Speech", "Pick a voice, pick a language, type text, listen.")
    engine = get_engine(settings, services)

    profiles = services.profiles.list()
    if not profiles:
        st.info("Create a voice profile first.")
        st.button("Go to Voice Profiles", on_click=components.go_to, args=("🎤 Voice Profiles",))
        return

    ready_to_run = _setup_gate(engine, settings, services)

    supported = services.languages.for_codes(engine.supported_language_codes()) or services.languages.all()
    c1, c2 = st.columns(2)
    profile = c1.selectbox("Voice profile", profiles, format_func=lambda p: p["profile_name"], key="gen_profile")
    language = c2.selectbox("Target language", supported, format_func=lambda l: f"{l.name} ({l.code})", key="gen_lang")
    with st.expander("Is your language missing?"):
        st.write("XTTS-v2 officially supports the languages in the list above. **Urdu is not officially supported**, and "
                 "this app never silently substitutes Hindi or Arabic. Another engine can be added in "
                 "`core/engines/`. The list itself can be changed with a `languages.json` file.")

    text = st.text_area("Text to speak (write it in the selected language — this app does not translate)",
                        height=170, key="gen_text", max_chars=config.MAX_TEXT_CHARS)
    chunk_limit = max(int(language.char_limit * 0.9), 20)
    parts = len(chunk_text(text, chunk_limit)) if text.strip() else 0
    st.caption(f"{len(text)}/{config.MAX_TEXT_CHARS} characters · {parts} part(s) · per-part limit for "
               f"{language.name}: ~{chunk_limit} characters")

    with st.expander("Voice & quality settings (optional)"):
        st.caption("Defaults come from Settings. Changes here apply to this session only.")
        s = synthesis_settings(settings)
        s.temperature = st.slider("Temperature (variation)", 0.1, 1.2, float(s.temperature), 0.05)
        s.speed = st.slider("Speed", 0.7, 1.3, float(s.speed), 0.05)
        s.repetition_penalty = st.slider("Repetition penalty", 1.0, 10.0, float(s.repetition_penalty), 0.5)

    st.caption(components.AI_NOTICE)
    if st.button("🎧 Generate speech", type="primary", disabled=not ready_to_run or not text.strip()):
        bar = st.progress(0.0, text="Starting…")

        def on_progress(done: int, total: int, message: str) -> None:
            bar.progress(min(done / max(total, 1), 1.0), text=message)

        try:
            with st.spinner("Generating… the first run also loads the model, which can take a few minutes."):
                result = services.generator.generate(
                    engine=engine, profile_id=profile["id"], text=text, language=language.code, settings=s,
                    output_format=settings.output_format, mp3_bitrate=settings.mp3_bitrate, progress=on_progress)
            bar.progress(1.0, text="Done")
            st.session_state["last_generation_id"] = result.generation_id
            for w in result.warnings:
                st.warning(w)
            st.success(f"Generated {format_duration(result.duration_sec)} of audio in {result.elapsed_sec:.0f}s "
                       f"({result.chunk_count} part(s)).")
        except model_manager.InsufficientMemoryError as exc:
            bar.empty(); st.error(f"Out of memory: {exc}")
        except (model_manager.DependencyMissingError, model_manager.ModelLoadError) as exc:
            bar.empty(); st.error(str(exc))
        except (ValidationError, UnsupportedLanguageError, AudioError, EngineError) as exc:
            bar.empty(); st.error(str(exc))

    last_id = st.session_state.get("last_generation_id")
    record = services.db.get_generation(last_id) if last_id else None
    if record and services.storage.exists(record["output_audio_path"]):
        st.subheader("Result")
        audio_with_downloads(services.storage.local_path(record["output_audio_path"]),
                             f"{slugify(record['profile_name'])}_{record['language']}_{record['id']}",
                             f"gen{record['id']}", settings.mp3_bitrate)
        st.caption("Saved to your Audio Library. On Streamlit Community Cloud, storage is temporary — download files you want to keep.")
