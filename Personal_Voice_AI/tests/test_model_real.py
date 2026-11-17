"""REAL XTTS-v2 tests (no fakes). Skipped automatically unless the model stack is installed.

Run:   set RUN_MODEL_TESTS=1   (Windows)   /   RUN_MODEL_TESTS=1 pytest -m model   (Linux/macOS)
The first run downloads ~1.8 GB. You must have accepted the Coqui licence (COQUI_TOS_AGREED=1).
"""
import os

import pytest

from core import model_manager

pytestmark = pytest.mark.model
STACK = not model_manager.missing_dependencies()
ENABLED = os.environ.get("RUN_MODEL_TESTS") == "1"
skip = pytest.mark.skipif(not (STACK and ENABLED), reason="needs requirements-xtts.txt and RUN_MODEL_TESTS=1")


@skip
def test_model_loads_and_generates_real_speech(tmp_path, speech_wav):
    from core import audio_processor
    from core.engines.base import SynthesisSettings
    from core.engines.xtts_engine import XTTSEngine

    ref_src = tmp_path / "in.wav"
    ref_src.write_bytes(speech_wav)
    ref = tmp_path / "ref.wav"
    audio_processor.prepare_reference(ref_src, ref)

    engine = XTTSEngine(device="auto")
    engine.load()
    assert engine.is_loaded
    wav, sr = engine.synthesize(["Hello, how are you today?"], ref, "en", SynthesisSettings())
    assert sr >= 16000 and len(wav) / sr > 0.5
    out = audio_processor.export_audio(wav, sr, tmp_path / "out.wav")
    assert out.stat().st_size > 10_000
