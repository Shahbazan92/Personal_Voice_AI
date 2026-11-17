"""Voice-profile lifecycle: create, rename, replace recording, delete."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from core import audio_processor
from core.audio_processor import AudioReport
from core.storage import StorageBackend
from database.database import Database
from utils.helpers import format_timestamp, utc_now_iso
from utils.validators import ValidationError, validate_profile_name, validate_upload


class ConsentRequiredError(ValidationError):
    pass


class ProfileService:
    def __init__(self, db: Database, storage: StorageBackend) -> None:
        self.db, self.storage = db, storage

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def folder_for(profile_id: int) -> str:
        return f"profiles/profile_{profile_id:03d}"

    def get(self, profile_id: int) -> dict:
        profile = self.db.get_profile(profile_id)
        if profile is None:
            raise ValidationError("That voice profile no longer exists.")
        return profile

    def reference_path(self, profile_id: int) -> Path:
        return self.storage.local_path(self.get(profile_id)["reference_audio_path"])

    def _write_profile_json(self, profile_id: int) -> None:
        p = self.get(profile_id)
        meta = {
            "id": p["id"],
            "profile_name": p["profile_name"],
            "created_at": p["created_at"],
            "updated_at": p["updated_at"],
            "duration_sec": p["duration_sec"],
            "consent_confirmed": bool(p["consent_confirmed"]),
            "reference": Path(p["reference_audio_path"]).name,
            "original": Path(p["original_audio_path"]).name if p["original_audio_path"] else None,
        }
        self.storage.put_bytes(json.dumps(meta, indent=2).encode("utf-8"), f"{self.folder_for(profile_id)}/profile.json")

    def _store_recording(self, profile_id: int, filename: str, data: bytes, noise_reduction: bool) -> AudioReport:
        ext = validate_upload(filename, data)
        folder = self.folder_for(profile_id)
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / f"original.{ext}"
            original.write_bytes(data)
            processed = Path(tmp) / "reference.wav"
            report = audio_processor.prepare_reference(original, processed, noise_reduction)
            original_key = self.storage.put_file(original, f"{folder}/original.{ext}")
            reference_key = self.storage.put_file(processed, f"{folder}/reference.wav")
        self.db.update_profile(
            profile_id,
            reference_audio_path=reference_key,
            original_audio_path=original_key,
            duration_sec=report.duration,
        )
        return report

    # -------------------------------------------------------------------- API
    def create(self, name: str, filename: str, data: bytes, consent: bool, noise_reduction: bool = False) -> tuple[int, AudioReport]:
        if not consent:
            raise ConsentRequiredError("You must confirm that this is your own voice or that you have explicit permission.")
        name = validate_profile_name(name)
        validate_upload(filename, data)  # fail early, before touching the database
        profile_id = self.db.add_profile(name, consent_confirmed=True)
        try:
            report = self._store_recording(profile_id, filename, data, noise_reduction)
            self._write_profile_json(profile_id)
        except Exception:
            # roll back: never leave a half-created profile or orphan files behind
            self.db.delete_profile(profile_id)
            self.storage.delete_prefix(self.folder_for(profile_id))
            raise
        return profile_id, report

    def rename(self, profile_id: int, new_name: str) -> None:
        self.db.update_profile(profile_id, profile_name=validate_profile_name(new_name))
        self._write_profile_json(profile_id)

    def replace_recording(self, profile_id: int, filename: str, data: bytes, noise_reduction: bool = False) -> AudioReport:
        old = self.get(profile_id)
        old_keys = {old["reference_audio_path"], old["original_audio_path"]} - {""}
        report = self._store_recording(profile_id, filename, data, noise_reduction)
        new = self.get(profile_id)
        for key in old_keys - {new["reference_audio_path"], new["original_audio_path"]}:
            self.storage.delete(key)  # e.g. the previous original.mp3 when the new one is .wav
        self._write_profile_json(profile_id)
        return report

    def delete(self, profile_id: int) -> None:
        """Delete the profile and ITS folder only. Generated audio is kept (profile link is cleared)."""
        self.get(profile_id)
        self.db.delete_profile(profile_id)
        self.storage.delete_prefix(self.folder_for(profile_id))

    def list(self) -> list[dict]:
        return self.db.list_profiles()

    @staticmethod
    def describe(profile: dict) -> str:
        return f"{profile['profile_name']} · created {format_timestamp(profile['created_at'])}"
