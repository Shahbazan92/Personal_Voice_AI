"""Input validation for uploads, names and text."""
from __future__ import annotations

from pathlib import Path

import config


class ValidationError(ValueError):
    """Raised when user input is rejected. The message is safe to show to the user."""


def get_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower().lstrip(".")


def sniff_audio_format(header: bytes) -> str | None:
    """Identify an audio container from its first bytes (not just its file name)."""
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE":
        return "wav"
    if header[:4] == b"fLaC":
        return "flac"
    if header[:3] == b"ID3" or (len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0):
        return "mp3"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return "m4a"
    return None


def validate_upload(filename: str, data: bytes) -> str:
    """Validate an uploaded/recorded file and return its normalised extension."""
    ext = get_extension(filename)
    if ext not in config.ALLOWED_EXTENSIONS:
        allowed = ", ".join(e.upper() for e in config.ALLOWED_EXTENSIONS)
        raise ValidationError(f"Unsupported file type '.{ext or '?'}'. Allowed formats: {allowed}.")
    if not data:
        raise ValidationError("The file is empty.")
    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise ValidationError(f"The file is larger than the {config.MAX_UPLOAD_MB} MB limit.")
    detected = sniff_audio_format(data[:16])
    if detected is None:
        raise ValidationError("The file content does not look like WAV, MP3, M4A or FLAC audio.")
    if detected != ext and not (detected == "m4a" and ext in ("m4a",)):
        # Extension and content disagree (e.g. an .mp3 that is really a WAV). Trust the
        # content: ffmpeg/soundfile probe the real format, so this is harmless, but we
        # still tell the caller which format was detected.
        return detected
    return ext


def validate_profile_name(name: str) -> str:
    cleaned = " ".join((name or "").split())
    if len(cleaned) < 2:
        raise ValidationError("Profile name must be at least 2 characters.")
    if len(cleaned) > 60:
        raise ValidationError("Profile name must be at most 60 characters.")
    return cleaned


def validate_text(text: str, max_chars: int | None = None) -> str:
    limit = max_chars or config.MAX_TEXT_CHARS
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValidationError("Please enter some text.")
    if len(cleaned) > limit:
        raise ValidationError(
            f"Text is {len(cleaned)} characters long; the limit is {limit}. "
            "Split it into several generations."
        )
    return cleaned
