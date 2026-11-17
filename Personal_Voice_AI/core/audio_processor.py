"""Audio loading, validation, cleaning, conversion and export.

The original upload is never modified: ``prepare_reference`` writes a processed copy.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf

import config


class AudioError(RuntimeError):
    """Raised for unreadable / unusable audio. Message is user-safe."""


@dataclass
class AudioReport:
    duration: float
    sample_rate: int
    peak_dbfs: float
    rms_dbfs: float
    clipping_ratio: float
    snr_db: float
    silence_ratio: float
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def quality_label(self) -> str:
        if self.errors:
            return "Unusable"
        if len(self.warnings) >= 2:
            return "Fair"
        if self.warnings:
            return "Good"
        return "Excellent"


# ------------------------------------------------------------------- ffmpeg
def find_ffmpeg() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:  # bundled binary from the `imageio-ffmpeg` package
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 - optional dependency, any failure means "not available"
        return None


def ffmpeg_available() -> bool:
    return find_ffmpeg() is not None


def _run_ffmpeg(args: list[str]) -> None:
    exe = find_ffmpeg()
    if exe is None:
        raise AudioError("FFmpeg is required for this operation but was not found. See the README.")
    proc = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise AudioError(f"FFmpeg failed: {proc.stderr.strip()[:300] or 'unknown error'}")


# ------------------------------------------------------------------ loading
def _read_with_soundfile(path: Path) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), always_2d=True, dtype="float32")
    return data.mean(axis=1), int(sr)


def load_audio(path: Path) -> tuple[np.ndarray, int]:
    """Load any supported file as mono float32. Falls back to FFmpeg for M4A/odd MP3s."""
    path = Path(path)
    try:
        y, sr = _read_with_soundfile(path)
    except Exception as sf_error:  # noqa: BLE001 - libsndfile raises several types
        if not ffmpeg_available():
            raise AudioError(
                f"Could not read this audio file ({sf_error}). Install FFmpeg to enable "
                "M4A/MP3 decoding, or upload a WAV/FLAC file."
            ) from sf_error
        with tempfile.TemporaryDirectory() as tmp:
            converted = Path(tmp) / "converted.wav"
            _run_ffmpeg(["-i", str(path), "-vn", "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", str(converted)])
            try:
                y, sr = _read_with_soundfile(converted)
            except Exception as exc:  # noqa: BLE001
                raise AudioError(f"The audio file appears to be corrupted: {exc}") from exc
    if y.size == 0:
        raise AudioError("The audio file contains no samples.")
    if not np.all(np.isfinite(y)):
        raise AudioError("The audio file contains invalid sample values.")
    return y.astype(np.float32), sr


# ---------------------------------------------------------------- analysis
def _db(value: float) -> float:
    return float(20.0 * np.log10(max(value, 1e-9)))


def analyze(y: np.ndarray, sr: int) -> AudioReport:
    duration = len(y) / sr
    peak = float(np.max(np.abs(y)))
    rms = float(np.sqrt(np.mean(np.square(y))))
    clipping = float(np.mean(np.abs(y) >= 0.999))

    frame, hop = max(int(0.025 * sr), 1), max(int(0.010 * sr), 1)
    if len(y) >= frame:
        idx = np.arange(0, len(y) - frame + 1, hop)
        frames = np.stack([y[i:i + frame] for i in idx[:: max(1, len(idx) // 4000)]])
        energy = np.sqrt(np.mean(np.square(frames), axis=1))
    else:
        energy = np.array([rms])
    energy_sorted = np.sort(energy)
    noise = float(np.mean(energy_sorted[: max(1, len(energy_sorted) // 10)]))
    signal = float(np.mean(energy_sorted[len(energy_sorted) // 2:]))
    snr = _db(signal) - _db(noise)
    silence_ratio = float(np.mean(energy < max(signal * 0.05, 1e-5)))

    report = AudioReport(duration, sr, _db(peak), _db(rms), clipping, snr, silence_ratio)

    if duration < config.MIN_REFERENCE_SECONDS:
        report.errors.append(f"Too short ({duration:.1f}s). At least {config.MIN_REFERENCE_SECONDS:.0f}s is required.")
    elif duration < config.RECOMMENDED_MIN_SECONDS:
        report.warnings.append(f"Short recording ({duration:.1f}s). 10–30 s of clear speech gives better results.")
    if duration > config.MAX_REFERENCE_SECONDS:
        report.errors.append(f"Too long ({duration:.0f}s). Maximum is {config.MAX_REFERENCE_SECONDS:.0f}s.")
    elif duration > config.RECOMMENDED_MAX_SECONDS:
        report.warnings.append("Long recording: XTTS-v2 only uses roughly the first 30 s for the voice.")
    if peak < 1e-4 or rms < 1e-5:
        report.errors.append("The recording is silent.")
    if clipping > 0.005:
        report.warnings.append("Audio is clipping (distorted). Record again with lower input volume.")
    if report.rms_dbfs < -40 and not report.errors:
        report.warnings.append("Recording is very quiet. It will be normalised, but noise may be amplified.")
    if snr < 15 and not report.errors:
        report.warnings.append(f"Background noise looks high (estimated SNR {snr:.0f} dB). Try a quieter room or enable noise reduction.")
    if silence_ratio > 0.5 and not report.errors:
        report.warnings.append("More than half of the recording is silence.")
    return report


def inspect_file(path: Path) -> AudioReport:
    y, sr = load_audio(path)
    return analyze(y, sr)


# -------------------------------------------------------------- processing
def reduce_noise(y: np.ndarray, sr: int) -> np.ndarray:
    try:
        import noisereduce as nr
    except ImportError as exc:
        raise AudioError("Noise reduction needs the 'noisereduce' package (pip install noisereduce).") from exc
    return nr.reduce_noise(y=y, sr=sr, stationary=True, prop_decrease=0.8).astype(np.float32)


def trim_silence(y: np.ndarray, sr: int, top_db: float = 35.0) -> np.ndarray:
    import librosa

    trimmed, _ = librosa.effects.trim(y, top_db=top_db)
    return trimmed if len(trimmed) >= sr * config.MIN_REFERENCE_SECONDS * 0.8 else y


def resample(y: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    if orig_sr == target_sr:
        return y
    import librosa

    return librosa.resample(y, orig_sr=orig_sr, target_sr=target_sr).astype(np.float32)


def normalize_loudness(y: np.ndarray, target_rms_dbfs: float = config.TARGET_RMS_DBFS, ceiling: float = 0.97) -> np.ndarray:
    rms = float(np.sqrt(np.mean(np.square(y))))
    if rms < 1e-6:
        raise AudioError("Cannot normalise a silent recording.")
    out = y * (10 ** (target_rms_dbfs / 20) / rms)
    peak = float(np.max(np.abs(out)))
    if peak > ceiling:
        out = out * (ceiling / peak)
    return out.astype(np.float32)


def write_wav(y: np.ndarray, sr: int, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.clip(y, -1.0, 1.0), sr, subtype="PCM_16")


def prepare_reference(source: Path, destination: Path, noise_reduction: bool = False) -> AudioReport:
    """Create a cleaned, normalised mono WAV copy of ``source`` at ``destination``.

    Raises ``AudioError`` if the raw audio fails validation. Returns a report of the result.
    """
    y, sr = load_audio(source)
    raw_report = analyze(y, sr)
    if not raw_report.ok:
        raise AudioError(" ".join(raw_report.errors))
    y = y - float(np.mean(y))  # remove DC offset
    if noise_reduction:
        y = reduce_noise(y, sr)
    y = trim_silence(y, sr)
    y = resample(y, sr, config.REFERENCE_SAMPLE_RATE)
    y = normalize_loudness(y)
    write_wav(y, config.REFERENCE_SAMPLE_RATE, destination)
    return analyze(y, config.REFERENCE_SAMPLE_RATE)


# ------------------------------------------------------------------ output
def concat_audio(chunks: list[np.ndarray], sr: int, gap_ms: int = config.CHUNK_GAP_MS) -> np.ndarray:
    if not chunks:
        raise AudioError("No audio was generated.")
    gap = np.zeros(int(sr * gap_ms / 1000), dtype=np.float32)
    fade = min(int(sr * 0.005), min(len(c) for c in chunks) // 2)
    parts: list[np.ndarray] = []
    for i, chunk in enumerate(chunks):
        c = np.asarray(chunk, dtype=np.float32).copy()
        if fade > 0:
            ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
            c[:fade] *= ramp
            c[-fade:] *= ramp[::-1]
        parts.append(c)
        if i < len(chunks) - 1:
            parts.append(gap)
    return np.concatenate(parts)


def export_audio(y: np.ndarray, sr: int, path: Path, fmt: str = "wav", mp3_bitrate: str = "192k") -> Path:
    fmt = fmt.lower()
    path = Path(path)
    if fmt == "wav":
        write_wav(y, sr, path)
    elif fmt == "mp3":
        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "tmp.wav"
            write_wav(y, sr, wav_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            _run_ffmpeg(["-i", str(wav_path), "-codec:a", "libmp3lame", "-b:a", mp3_bitrate, str(path)])
    else:
        raise AudioError(f"Unsupported output format: {fmt}")
    return path


def convert_file_to_bytes(source: Path, fmt: str, mp3_bitrate: str = "192k") -> bytes:
    """Convert a stored audio file to ``fmt`` in memory (used for alternate downloads)."""
    fmt = fmt.lower()
    source = Path(source)
    if source.suffix.lower().lstrip(".") == fmt:
        return source.read_bytes()
    y, sr = load_audio(source)
    with tempfile.TemporaryDirectory() as tmp:
        out = export_audio(y, sr, Path(tmp) / f"out.{fmt}", fmt, mp3_bitrate)
        return out.read_bytes()
