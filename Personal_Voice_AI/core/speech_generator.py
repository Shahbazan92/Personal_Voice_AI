"""Orchestrates one generation: validate → chunk → synthesise → export → record."""
from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core import audio_processor
from core.engines.base import EngineError, ProgressCallback, SynthesisSettings, TTSEngine
from core.language_manager import LanguageManager
from core.profile_service import ProfileService
from core.storage import StorageBackend
from core.text_chunker import chunk_text
from database.database import Database
from utils.helpers import slugify
from utils.validators import validate_text

import config


@dataclass
class GenerationResult:
    generation_id: int
    key: str
    path: Path
    format: str
    duration_sec: float
    sample_rate: int
    chunk_count: int
    elapsed_sec: float
    profile_name: str
    language: str
    warnings: list[str]


class SpeechGenerator:
    def __init__(self, db: Database, storage: StorageBackend, languages: LanguageManager,
                 profiles: ProfileService) -> None:
        self.db, self.storage, self.languages, self.profiles = db, storage, languages, profiles

    def generate(
        self,
        *,
        engine: TTSEngine,
        profile_id: int,
        text: str,
        language: str,
        settings: SynthesisSettings,
        output_format: str = "wav",
        mp3_bitrate: str = "192k",
        progress: ProgressCallback | None = None,
    ) -> GenerationResult:
        started = time.time()
        warnings: list[str] = []
        text = validate_text(text, config.MAX_TEXT_CHARS)
        language = self.languages.validate(language, engine.supported_language_codes())
        profile = self.profiles.get(profile_id)
        reference = self.profiles.reference_path(profile_id)
        if not reference.is_file():
            raise EngineError("The reference recording for this profile is missing. Re-upload it on the Voice Profiles page.")

        # Chunks are packed to ~90 % of the language limit: fewer joins, still safe.
        limit = max(int(self.languages.char_limit(language) * 0.9), 20)
        chunks = chunk_text(text, limit)
        if not chunks:
            raise EngineError("Nothing to synthesise after cleaning the text.")

        waveform, sample_rate = engine.synthesize(chunks, reference, language, settings, progress)

        fmt = output_format.lower()
        if fmt == "mp3" and not audio_processor.ffmpeg_available():
            warnings.append("FFmpeg not found, so the file was saved as WAV instead of MP3.")
            fmt = "wav"

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        key = f"outputs/generated/{stamp}_{slugify(profile['profile_name'])}_{language}.{fmt}"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_file = Path(tmp) / f"out.{fmt}"
            audio_processor.export_audio(waveform, sample_rate, tmp_file, fmt, mp3_bitrate)
            self.storage.put_file(tmp_file, key)

        duration = len(waveform) / sample_rate
        gen_id = self.db.add_generation(
            profile_id=profile_id,
            profile_name=profile["profile_name"],
            input_text=text,
            language=language,
            output_audio_path=key,
            model_name=engine.name,
            duration_sec=duration,
        )
        return GenerationResult(gen_id, key, self.storage.local_path(key), fmt, duration, sample_rate,
                                len(chunks), time.time() - started, profile["profile_name"], language, warnings)

    def delete_generation(self, generation_id: int) -> bool:
        """Delete a history record and its audio file (only files inside storage are touched)."""
        record = self.db.get_generation(generation_id)
        if record is None:
            return False
        try:
            self.storage.delete(record["output_audio_path"])
        except Exception:  # noqa: BLE001 - a stale/invalid path must not block record removal
            pass
        return self.db.delete_generation(generation_id)
