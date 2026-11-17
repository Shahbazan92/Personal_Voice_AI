"""Shared, cached service objects for the Streamlit UI."""
from __future__ import annotations

import os
from dataclasses import dataclass

import streamlit as st

import config
from core import model_manager
from core.engines.base import SynthesisSettings, TTSEngine
from core.language_manager import LanguageManager
from core.profile_service import ProfileService
from core.settings import AppSettings
from core.speech_generator import SpeechGenerator
from core.storage import LocalStorage, StorageBackend
from core.voice_cloner import build_engine, resolve_engine_name
from database.database import Database


@dataclass
class Services:
    db: Database
    storage: StorageBackend
    languages: LanguageManager
    profiles: ProfileService
    generator: SpeechGenerator


@st.cache_resource(show_spinner=False)
def get_services() -> Services:
    config.ensure_directories()
    db = Database(config.DB_PATH)
    # To use persistent cloud storage, return your own StorageBackend here.
    storage = LocalStorage(config.DATA_DIR)
    languages = LanguageManager()
    profiles = ProfileService(db, storage)
    return Services(db, storage, languages, profiles, SpeechGenerator(db, storage, languages, profiles))


def load_settings() -> AppSettings:
    return AppSettings.load(config.SETTINGS_PATH)


def remote_credentials(settings: AppSettings) -> tuple[str, str]:
    """URL from settings / secrets / env; API key from session, secrets or env (never disk)."""
    url = settings.remote_url or os.environ.get(config.REMOTE_URL_ENV, "")
    key = st.session_state.get("remote_api_key", "") or os.environ.get(config.REMOTE_KEY_ENV, "")
    try:  # st.secrets raises if no secrets file exists
        url = url or st.secrets.get("remote_url", "")
        key = key or st.secrets.get("remote_api_key", "")
    except Exception:  # noqa: BLE001
        pass
    return url, key


@st.cache_resource(show_spinner=False)
def _cached_engine(name: str, device: str, url: str, key: str, codes: tuple[str, ...]) -> TTSEngine:
    return build_engine(name, device=device, remote_url=url, remote_key=key, language_codes=list(codes))


def get_engine(settings: AppSettings, services: Services) -> TTSEngine:
    """Return the (cached, load-once) engine selected in Settings."""
    url, key = remote_credentials(settings)
    name = resolve_engine_name(settings.engine, url)
    return _cached_engine(name, settings.device, url, key, tuple(services.languages.codes()))


def synthesis_settings(settings: AppSettings) -> SynthesisSettings:
    return SynthesisSettings(settings.temperature, settings.top_p, settings.top_k,
                             settings.repetition_penalty, settings.speed)


def apply_license_acceptance(settings: AppSettings) -> None:
    if settings.coqui_license_accepted:
        model_manager.accept_coqui_license()
