"""Central configuration for Personal Voice AI Studio.

Everything that touches the file system is derived from ``DATA_DIR`` so the
same code runs unchanged on a laptop, a GPU server or Streamlit Community Cloud.

Environment variables (all optional):

    PVAI_DATA_DIR        Root folder for profiles, outputs, database, models.
    PVAI_MAX_TEXT_CHARS  Maximum characters accepted per generation (default 3000).
    PVAI_MAX_UPLOAD_MB   Maximum upload size in MB (default 50).
    PVAI_REMOTE_URL      Base URL of a remote GPU inference server.
    PVAI_REMOTE_API_KEY  API key for the remote server (never stored on disk).
    TTS_HOME             Where Coqui downloads models (default: <DATA_DIR>/models).
"""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Personal Voice AI Studio"
APP_VERSION = "1.0.0"
APP_ICON = "🎙️"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("PVAI_DATA_DIR", str(BASE_DIR))).expanduser().resolve()

PROFILES_DIR = DATA_DIR / "profiles"
OUTPUTS_DIR = DATA_DIR / "outputs" / "generated"
DB_DIR = DATA_DIR / "data"
DB_PATH = DB_DIR / "voice_studio.db"
SETTINGS_PATH = DB_DIR / "settings.json"
MODELS_DIR = Path(os.environ.get("TTS_HOME", str(DATA_DIR / "models"))).expanduser()
LANGUAGES_OVERRIDE_PATH = DATA_DIR / "languages.json"

# Tell Coqui where to store the (≈1.8 GB) XTTS-v2 checkpoint. Must be set
# before the first model download. The user can still override via TTS_HOME.
os.environ.setdefault("TTS_HOME", str(MODELS_DIR))

# ---------------------------------------------------------------- audio rules
ALLOWED_EXTENSIONS = ("wav", "mp3", "m4a", "flac")
MAX_UPLOAD_MB = int(os.environ.get("PVAI_MAX_UPLOAD_MB", "50"))
MIN_REFERENCE_SECONDS = 5.0       # below this the upload is rejected
RECOMMENDED_MIN_SECONDS = 10.0    # below this a warning is shown
RECOMMENDED_MAX_SECONDS = 60.0    # XTTS only uses ~30 s anyway
MAX_REFERENCE_SECONDS = 300.0     # above this the upload is rejected
REFERENCE_SAMPLE_RATE = 22050     # XTTS-v2 conditioning sample rate
TARGET_RMS_DBFS = -20.0

# ----------------------------------------------------------------- generation
MAX_TEXT_CHARS = int(os.environ.get("PVAI_MAX_TEXT_CHARS", "3000"))
CHUNK_GAP_MS = 120

XTTS_MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
XTTS_LICENSE_URL = "https://coqui.ai/cpml"

# ------------------------------------------------------------------ remote GPU
REMOTE_URL_ENV = "PVAI_REMOTE_URL"
REMOTE_KEY_ENV = "PVAI_REMOTE_API_KEY"


def ensure_directories() -> None:
    """Create the folders the app writes to (idempotent)."""
    for folder in (PROFILES_DIR, OUTPUTS_DIR, DB_DIR, MODELS_DIR):
        folder.mkdir(parents=True, exist_ok=True)
