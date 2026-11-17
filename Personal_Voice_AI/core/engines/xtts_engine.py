"""Local Coqui XTTS-v2 engine (real inference, CPU or CUDA)."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

import numpy as np

from core import model_manager
from core.engines.base import EngineError, ProgressCallback, SynthesisSettings, TTSEngine
from core.language_manager import DEFAULT_LANGUAGES


class XTTSEngine(TTSEngine):
    name = "xtts_v2"
    label = "Coqui XTTS-v2 (local)"
    description = "Multilingual zero-shot voice cloning from a short reference recording."
    runs_locally = True

    def __init__(self, device: str = "auto", language_codes: list[str] | None = None) -> None:
        self.device_preference = device
        self._codes = language_codes or [lang.code for lang in DEFAULT_LANGUAGES]
        self._tts = None
        self._latents: dict[tuple, tuple] = {}
        self._lock = threading.Lock()  # the model is not thread-safe

    # --------------------------------------------------------------- interface
    def is_available(self) -> tuple[bool, str]:
        missing = model_manager.missing_dependencies()
        if missing:
            return False, "Missing packages: " + ", ".join(missing)
        return True, ""

    def supported_language_codes(self) -> list[str]:
        return list(self._codes)

    @property
    def is_loaded(self) -> bool:
        return self._tts is not None

    @property
    def device(self) -> str:
        return model_manager.detect_device(self.device_preference)

    def load(self, progress: Callable[[str], None] | None = None) -> None:
        with self._lock:
            if self._tts is None:
                self._tts = model_manager.load_xtts(self.device_preference, progress)

    # ---------------------------------------------------------------- internals
    def _conditioning(self, reference_path: Path):
        """Compute (and cache) speaker latents once per reference file.

        Re-using identical latents for every chunk is what keeps the voice
        consistent across a long text.
        """
        stat = reference_path.stat()
        key = (str(reference_path), stat.st_mtime_ns, stat.st_size)
        if key not in self._latents:
            model = self._tts.synthesizer.tts_model
            self._latents[key] = model.get_conditioning_latents(audio_path=[str(reference_path)])
            if len(self._latents) > 16:  # tiny LRU-ish bound
                self._latents.pop(next(iter(self._latents)))
        return self._latents[key]

    @staticmethod
    def _to_numpy(wav) -> np.ndarray:
        if hasattr(wav, "detach"):
            wav = wav.detach().cpu().numpy()
        return np.asarray(wav, dtype=np.float32).squeeze()

    def _sample_rate(self) -> int:
        try:
            return int(self._tts.synthesizer.output_sample_rate)
        except Exception:  # noqa: BLE001
            return 24000  # documented XTTS-v2 output rate

    # ---------------------------------------------------------------- synthesis
    def synthesize(
        self,
        chunks: list[str],
        reference_path: Path,
        language: str,
        settings: SynthesisSettings,
        progress: ProgressCallback | None = None,
    ) -> tuple[np.ndarray, int]:
        reference_path = Path(reference_path)
        if not reference_path.is_file():
            raise EngineError("The reference recording for this profile is missing on disk.")
        if language not in self._codes:
            raise EngineError(f"XTTS-v2 does not support language '{language}'.")
        self.load()

        waves: list[np.ndarray] = []
        try:
            with self._lock:
                model = self._tts.synthesizer.tts_model
                use_low_level = hasattr(model, "get_conditioning_latents") and hasattr(model, "inference")
                if use_low_level:
                    gpt_latent, speaker_emb = self._conditioning(reference_path)
                for i, chunk in enumerate(chunks):
                    if progress:
                        progress(i, len(chunks), f"Synthesising part {i + 1} of {len(chunks)}…")
                    if use_low_level:
                        out = model.inference(
                            text=chunk,
                            language=language,
                            gpt_cond_latent=gpt_latent,
                            speaker_embedding=speaker_emb,
                            temperature=settings.temperature,
                            length_penalty=1.0,
                            repetition_penalty=settings.repetition_penalty,
                            top_k=settings.top_k,
                            top_p=settings.top_p,
                            speed=settings.speed,
                            enable_text_splitting=False,
                        )
                        wav = out["wav"]
                    else:  # public high-level API fallback for other library versions
                        wav = self._tts.tts(text=chunk, speaker_wav=str(reference_path),
                                            language=language, split_sentences=False)
                    waves.append(self._to_numpy(wav))
        except Exception as exc:  # noqa: BLE001 - classified below, never swallowed
            if model_manager.is_oom_error(exc):
                model_manager.free_cuda_cache()
                raise model_manager.InsufficientMemoryError(
                    "Ran out of memory during generation. Try shorter text, use CPU, or use a machine with more memory."
                ) from exc
            raise EngineError(f"XTTS-v2 inference failed: {exc}") from exc

        if progress:
            progress(len(chunks), len(chunks), "Finalising audio…")
        from core.audio_processor import concat_audio

        return concat_audio(waves, self._sample_rate()), self._sample_rate()
