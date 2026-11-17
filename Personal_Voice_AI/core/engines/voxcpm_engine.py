"""VoxCPM2 integration point (NOT implemented yet — intentionally).

The task requires that no unsupported/invented APIs are used. The official VoxCPM
repository (https://github.com/OpenBMB/VoxCPM) must be checked for the real,
current inference interface of the VoxCPM2 release before this is filled in.

To finish the integration:
  1. Add the package to a new ``requirements-voxcpm.txt`` (version from the official README).
  2. Implement ``load`` (download / load the checkpoint) and ``synthesize`` below,
     returning ``(mono float32 numpy waveform, sample_rate)`` exactly like ``XTTSEngine``.
  3. Declare the languages VoxCPM2 documents in ``supported_language_codes``.
  4. Make ``is_available`` return ``(True, "")`` once the package imports.
The UI, history, chunking and storage need no changes: the engine registry in
``core/voice_cloner.py`` already lists this engine.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np

from core.engines.base import EngineError, ProgressCallback, SynthesisSettings, TTSEngine


class VoxCPM2Engine(TTSEngine):
    name = "voxcpm2"
    label = "VoxCPM2 (not integrated yet)"
    description = "Planned secondary engine. See core/engines/voxcpm_engine.py for the integration steps."
    runs_locally = True

    def is_available(self) -> tuple[bool, str]:
        return False, "VoxCPM2 is not integrated yet. Use XTTS-v2 (see core/engines/voxcpm_engine.py)."

    def supported_language_codes(self) -> list[str]:
        return []

    @property
    def is_loaded(self) -> bool:
        return False

    def load(self, progress: Callable[[str], None] | None = None) -> None:
        raise EngineError(self.is_available()[1])

    def synthesize(self, chunks: list[str], reference_path: Path, language: str,
                   settings: SynthesisSettings, progress: ProgressCallback | None = None) -> tuple[np.ndarray, int]:
        raise EngineError(self.is_available()[1])
