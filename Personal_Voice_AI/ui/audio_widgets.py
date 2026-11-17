"""Playback + download widgets shared by the Generate and Library pages."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from core import audio_processor

MIME = {"wav": "audio/wav", "mp3": "audio/mpeg"}


@st.cache_data(show_spinner=False, max_entries=16)
def _converted(path: str, mtime_ns: int, fmt: str, bitrate: str) -> bytes:
    return audio_processor.convert_file_to_bytes(Path(path), fmt, bitrate)


def audio_with_downloads(path: Path, stem: str, key: str, bitrate: str = "192k") -> None:
    """Player + download buttons for the stored format and (when possible) the other one."""
    path = Path(path)
    stored = path.suffix.lower().lstrip(".")
    st.audio(str(path))
    other = "mp3" if stored == "wav" else "wav"
    cols = st.columns(2)
    cols[0].download_button(f"⬇️ Download {stored.upper()}", data=path.read_bytes(), file_name=f"{stem}.{stored}",
                            mime=MIME.get(stored, "application/octet-stream"), key=f"dl_{key}_{stored}")
    if other == "wav" or audio_processor.ffmpeg_available():
        try:
            data = _converted(str(path), path.stat().st_mtime_ns, other, bitrate)
            cols[1].download_button(f"⬇️ Download {other.upper()}", data=data, file_name=f"{stem}.{other}",
                                    mime=MIME[other], key=f"dl_{key}_{other}")
        except audio_processor.AudioError as exc:
            cols[1].caption(f"{other.upper()} unavailable: {exc}")
    else:
        cols[1].caption("MP3 download needs FFmpeg (not found).")
