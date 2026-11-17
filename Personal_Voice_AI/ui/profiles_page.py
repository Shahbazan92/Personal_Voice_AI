from __future__ import annotations

import streamlit as st

import config
from core import audio_processor
from core.audio_processor import AudioError
from core.profile_service import ConsentRequiredError
from database.database import DuplicateProfileError
from ui import components
from ui.services import Services
from utils.helpers import format_duration, format_timestamp, sha256_bytes
from utils.validators import ValidationError, validate_upload


@st.cache_data(show_spinner=False, max_entries=8)
def _inspect(data_hash: str, filename: str, data: bytes):
    """Analyse an upload once per distinct file (not on every Streamlit rerun)."""
    import tempfile
    from pathlib import Path

    ext = validate_upload(filename, data)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"in.{ext}"
        path.write_bytes(data)
        return audio_processor.inspect_file(path)


def _audio_input(label: str, key: str):
    """Upload or record; returns (filename, bytes) or None."""
    mode = st.radio("Voice source", ["Upload a file", "Record with microphone"], horizontal=True, key=f"{key}_mode")
    if mode == "Upload a file":
        up = st.file_uploader(f"Audio file ({', '.join(e.upper() for e in config.ALLOWED_EXTENSIONS)})",
                              type=list(config.ALLOWED_EXTENSIONS), key=f"{key}_upload")
        return (up.name, up.getvalue()) if up else None
    st.caption("Read a few natural sentences for 15–30 seconds in a quiet room, one speaker only.")
    rec = st.audio_input(label, key=f"{key}_record")
    return ("recording.wav", rec.getvalue()) if rec else None


def _create_tab(services: Services, settings) -> None:
    nonce = st.session_state.setdefault("create_nonce", 0)
    key = f"create_{nonce}"
    st.markdown("**Recommended:** 10–30 s of clear speech, minimal background noise, one speaker.")
    name = st.text_input("Profile name", key=f"{key}_name", max_chars=60, placeholder="e.g. My English voice")
    source = _audio_input("Record your voice", key)

    report = None
    if source:
        filename, data = source
        try:
            report = _inspect(sha256_bytes(data), filename, data)
            st.audio(data)
            components.show_report(report)
        except (ValidationError, AudioError) as exc:
            st.error(str(exc))

    denoise = st.checkbox("Reduce background noise (stationary noise)", value=settings.noise_reduction_default, key=f"{key}_nr")
    consent = st.checkbox("I confirm this is my own voice, or I have explicit permission from the speaker to clone it, "
                          "and I will not use it to impersonate or deceive anyone.", key=f"{key}_consent")
    can_save = bool(source and report and report.ok and name.strip() and consent)
    if st.button("💾 Save voice profile", type="primary", disabled=not can_save, key=f"{key}_save"):
        try:
            with st.spinner("Processing and saving your voice…"):
                _, saved_report = services.profiles.create(name, source[0], source[1], consent, denoise)
            st.session_state["create_nonce"] = nonce + 1
            st.session_state["flash"] = f"Profile '{name.strip()}' saved ({saved_report.duration:.1f} s of processed audio)."
            st.rerun()
        except (ValidationError, DuplicateProfileError, ConsentRequiredError, AudioError) as exc:
            st.error(str(exc))
    if not can_save:
        st.caption("To save: enter a name, add a valid recording and tick the consent box.")


def _manage_tab(services: Services, settings) -> None:
    profiles = services.profiles.list()
    if not profiles:
        st.info("No voice profiles yet. Create one in the first tab.")
        return
    for p in profiles:
        pid = p["id"]
        with st.expander(f"🎤 {p['profile_name']} — {format_duration(p['duration_sec'])} · created {format_timestamp(p['created_at'])}"):
            ref = services.storage.local_path(p["reference_audio_path"]) if p["reference_audio_path"] else None
            if ref and ref.is_file():
                st.audio(str(ref))
            else:
                st.warning("The reference recording is missing from storage. Replace it below.")

            c1, c2 = st.columns([3, 1])
            new_name = c1.text_input("Rename", value=p["profile_name"], key=f"rn_{pid}", max_chars=60)
            if c2.button("Rename", key=f"rnb_{pid}", disabled=new_name.strip() == p["profile_name"]):
                try:
                    services.profiles.rename(pid, new_name)
                    st.rerun()
                except (ValidationError, DuplicateProfileError) as exc:
                    st.error(str(exc))

            st.markdown("**Replace recording**")
            src = _audio_input("Record a replacement", f"rep_{pid}")
            denoise = st.checkbox("Reduce background noise", value=settings.noise_reduction_default, key=f"rep_nr_{pid}")
            if st.button("Replace recording", key=f"repb_{pid}", disabled=src is None):
                try:
                    with st.spinner("Processing…"):
                        services.profiles.replace_recording(pid, src[0], src[1], denoise)
                    st.session_state["flash"] = "Recording replaced."
                    st.rerun()
                except (ValidationError, AudioError) as exc:
                    st.error(str(exc))

            st.markdown("**Delete profile**")
            st.caption("Deletes this profile and its recordings. Audio you already generated stays in your library.")
            confirm = st.checkbox("Yes, permanently delete this profile", key=f"delc_{pid}")
            if st.button("🗑️ Delete profile", key=f"del_{pid}", disabled=not confirm):
                services.profiles.delete(pid)
                st.session_state["flash"] = f"Profile '{p['profile_name']}' deleted."
                st.rerun()


def render(services: Services, settings) -> None:
    components.hero("Voice Profiles", "Add your voice once; reuse it in every language.")
    if msg := st.session_state.pop("flash", None):
        st.success(msg)
    st.info("🔒 Recordings stay on this host. Nothing is sent to third parties unless you select the Remote GPU engine.")
    tab_new, tab_manage = st.tabs(["➕ Create profile", "🗂️ Manage profiles"])
    with tab_new:
        _create_tab(services, settings)
    with tab_manage:
        _manage_tab(services, settings)
