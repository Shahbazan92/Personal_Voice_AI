from __future__ import annotations

import streamlit as st

import config
from ui import components
from ui.services import Services


def render(services: Services, settings) -> None:
    components.hero("About", f"{config.APP_NAME} v{config.APP_VERSION}")
    st.subheader("How voice cloning works")
    st.write("A short reference recording is cleaned (resampled, loudness-normalised, optionally denoised). XTTS-v2 turns it "
             "into speaker *latents* describing timbre and speaking style. For each piece of your text the model generates "
             "speech conditioned on those latents, in the language you choose. The same latents are re-used for every part "
             "of a long text to keep the voice consistent. Cross-language output keeps your voice character but accent and "
             "prosody are approximate; results vary with recording quality.")
    st.info("Text-to-speech does not translate. Type your text in the target language.")

    st.subheader("Models")
    st.write("**Primary:** Coqui XTTS-v2 (`tts_models/multilingual/multi-dataset/xtts_v2`), licensed under the "
             f"[Coqui Public Model License]({config.XTTS_LICENSE_URL}) (non-commercial). "
             "**Secondary:** VoxCPM2 — an integration interface is prepared, but it is not implemented yet.")

    st.subheader("Supported languages")
    st.write(", ".join(f"{l.name} (`{l.code}`)" for l in services.languages.all()))
    st.caption("Urdu is not an officially supported XTTS-v2 language and is never substituted with Hindi or Arabic.")

    st.subheader("Privacy")
    st.write("Recordings and generated audio are stored in the app's data folder on the machine that runs it. Nothing is "
             "uploaded elsewhere, except to *your own* GPU server if you choose the Remote GPU engine. On Streamlit Community "
             "Cloud the disk is temporary and the app runs on shared infrastructure — do not upload sensitive recordings "
             "there unless you accept that, and never commit recordings to GitHub.")

    st.subheader("Responsible use")
    st.warning(components.AI_NOTICE)
