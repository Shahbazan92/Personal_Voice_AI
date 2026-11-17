"""Engine interface. Implement ``TTSEngine`` to plug in another voice-cloning model."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

ProgressCallback = Callable[[int, int, str], None]  # (done, total, message)


class EngineError(RuntimeError):
    """Raised by engines for any user-reportable failure."""


@dataclass
class SynthesisSettings:
    temperature: float = 0.75
    top_p: float = 0.85
    top_k: int = 50
    repetition_penalty: float = 5.0
    speed: float = 1.0


class TTSEngine(ABC):
    name: str = "base"
    label: str = "Base engine"
    description: str = ""
    runs_locally: bool = True

    @abstractmethod
    def is_available(self) -> tuple[bool, str]:
        """(ready_to_attempt, human-readable reason when not)."""

    @abstractmethod
    def supported_language_codes(self) -> list[str]: ...

    @abstractmethod
    def load(self, progress: Callable[[str], None] | None = None) -> None:
        """Load / connect. Must be idempotent and cheap when already loaded."""

    @property
    @abstractmethod
    def is_loaded(self) -> bool: ...

    @abstractmethod
    def synthesize(
        self,
        chunks: list[str],
        reference_path: Path,
        language: str,
        settings: SynthesisSettings,
        progress: ProgressCallback | None = None,
    ) -> tuple[np.ndarray, int]:
        """Return (mono float32 waveform, sample_rate) for all ``chunks`` in order."""
