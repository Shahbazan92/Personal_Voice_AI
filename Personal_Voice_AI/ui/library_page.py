from __future__ import annotations

import streamlit as st

from ui import components
from ui.audio_widgets import audio_with_downloads
from ui.services import Services
from utils.helpers import format_duration, format_timestamp, slugify

PAGE_SIZE = 10


def render(services: Services, settings) -> None:
    components.hero("Audio Library", "Everything you have generated.")
    st.caption("On Streamlit Community Cloud the file system is temporary; download anything you want to keep.")

    profiles = services.profiles.list()
    f1, f2 = st.columns(2)
    prof = f1.selectbox("Voice profile", [None, *profiles], format_func=lambda p: "All profiles" if p is None else p["profile_name"])
    lang = f2.selectbox("Language", [None, *services.languages.all()],
                        format_func=lambda l: "All languages" if l is None else f"{l.name} ({l.code})")

    total_filtered = len(services.db.list_generations(limit=100000, profile_id=prof["id"] if prof else None,
                                                      language=lang.code if lang else None))
    pages = max((total_filtered - 1) // PAGE_SIZE + 1, 1)
    page = st.number_input("Page", min_value=1, max_value=pages, value=1, step=1) if pages > 1 else 1
    records = services.db.list_generations(limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE,
                                           profile_id=prof["id"] if prof else None,
                                           language=lang.code if lang else None)
    if not records:
        st.info("No generated audio found.")
        return
    st.write(f"{total_filtered} file(s)")

    for rec in records:
        file_name = rec["output_audio_path"].rsplit("/", 1)[-1]
        with st.container(border=True):
            st.markdown(f"**{file_name}**")
            st.caption(f"{rec['profile_name'] or 'Deleted profile'} · {services.languages.name_for(rec['language'])} · "
                       f"{rec['model_name']} · {format_duration(rec['duration_sec'])} · {format_timestamp(rec['created_at'])}")
            st.write(rec["input_text"][:200] + ("…" if len(rec["input_text"]) > 200 else ""))
            if services.storage.exists(rec["output_audio_path"]):
                audio_with_downloads(services.storage.local_path(rec["output_audio_path"]),
                                     slugify(file_name.rsplit(".", 1)[0], 80), f"lib{rec['id']}", settings.mp3_bitrate)
            else:
                st.warning("Audio file is missing from storage (only the history record remains).")
            if st.button("🗑️ Delete", key=f"libdel_{rec['id']}"):
                services.generator.delete_generation(rec["id"])
                st.rerun()
