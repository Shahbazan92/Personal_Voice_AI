"""Test data helpers (synthetic audio only)."""
from __future__ import annotations

import io

import numpy as np


def make_speech_like(seconds: float = 12.0, sr: int = 22050, noise: float = 0.002) -> np.ndarray:
    """Synthetic 'speech-like' signal: amplitude-modulated harmonics + light noise (test data only)."""
    t = np.arange(int(seconds * sr)) / sr
    f0 = 140 + 20 * np.sin(2 * np.pi * 0.7 * t)
    phase = 2 * np.pi * np.cumsum(f0) / sr
    voice = sum(np.sin(k * phase) / k for k in range(1, 6))
    envelope = 0.5 * (1 + np.sin(2 * np.pi * 2.5 * t)) ** 2
    rng = np.random.default_rng(0)
    return (0.3 * voice * envelope + noise * rng.standard_normal(len(t))).astype(np.float32)


def wav_bytes(y: np.ndarray, sr: int = 22050) -> bytes:
    import soundfile as sf

    buf = io.BytesIO()
    sf.write(buf, y, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()
