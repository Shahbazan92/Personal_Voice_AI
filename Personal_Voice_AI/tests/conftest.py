"""Shared fixtures. Tests never touch your real profiles/outputs: they use a temp data dir."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

from tests.helpers import make_speech_like, wav_bytes

_TMP_ROOT = tempfile.mkdtemp(prefix="pvai_tests_")
os.environ["PVAI_DATA_DIR"] = _TMP_ROOT
os.environ["TTS_HOME"] = str(Path(_TMP_ROOT) / "models")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def speech_wav() -> bytes:
    return wav_bytes(make_speech_like(12.0))


@pytest.fixture
def short_wav() -> bytes:
    return wav_bytes(make_speech_like(1.5))


@pytest.fixture
def storage(tmp_path):
    from core.storage import LocalStorage

    return LocalStorage(tmp_path / "store")


@pytest.fixture
def db(tmp_path):
    from database.database import Database

    return Database(tmp_path / "test.db")


@pytest.fixture
def profiles(db, storage):
    from core.profile_service import ProfileService

    return ProfileService(db, storage)


class FakeEngine:
    """TEST-ONLY engine used to exercise the orchestration code without downloading a model.

    The real XTTS-v2 inference is covered by tests/test_model_real.py.
    """
    name = "fake"
    label = "Fake"

    def __init__(self):
        self.calls = []

    def is_available(self):
        return True, ""

    def supported_language_codes(self):
        return ["en", "es"]

    is_loaded = True

    def load(self, progress=None):
        pass

    def synthesize(self, chunks, reference_path, language, settings, progress=None):
        self.calls.append((list(chunks), str(reference_path), language))
        sr = 24000
        t = np.arange(int(0.5 * sr)) / sr
        tone = (np.sin(2 * np.pi * 220 * t) * 0.3).astype(np.float32)
        return np.concatenate([tone for _ in chunks]), sr


@pytest.fixture
def fake_engine():
    return FakeEngine()
