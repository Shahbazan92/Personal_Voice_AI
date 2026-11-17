import numpy as np
import pytest
import soundfile as sf

import config
from core import audio_processor as ap
from tests.helpers import make_speech_like, wav_bytes


def test_load_and_analyze_good_audio(tmp_path, speech_wav):
    path = tmp_path / "a.wav"
    path.write_bytes(speech_wav)
    report = ap.inspect_file(path)
    assert report.ok and 11.5 < report.duration < 12.5


def test_short_audio_is_rejected(tmp_path, short_wav):
    path = tmp_path / "s.wav"
    path.write_bytes(short_wav)
    assert not ap.inspect_file(path).ok
    with pytest.raises(ap.AudioError):
        ap.prepare_reference(path, tmp_path / "out.wav")


def test_silent_audio_is_rejected(tmp_path):
    path = tmp_path / "silent.wav"
    path.write_bytes(wav_bytes(np.zeros(22050 * 8, dtype=np.float32)))
    with pytest.raises(ap.AudioError):
        ap.prepare_reference(path, tmp_path / "out.wav")


def test_prepare_reference_normalizes_and_keeps_original(tmp_path):
    src = tmp_path / "quiet.wav"
    src.write_bytes(wav_bytes(make_speech_like(12.0) * 0.05, 44100))
    before = src.read_bytes()
    out = tmp_path / "ref.wav"
    ap.prepare_reference(src, out)
    y, sr = sf.read(out)
    assert sr == config.REFERENCE_SAMPLE_RATE and y.ndim == 1
    rms_db = 20 * np.log10(np.sqrt(np.mean(y ** 2)))
    assert -26 < rms_db < -14
    assert src.read_bytes() == before  # original untouched


def test_corrupt_file_raises_audio_error(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"RIFF....WAVEjunk")
    with pytest.raises(ap.AudioError):
        ap.load_audio(bad)


def test_concat_and_export_wav(tmp_path):
    chunks = [np.ones(2400, dtype=np.float32) * 0.2, np.ones(2400, dtype=np.float32) * 0.2]
    joined = ap.concat_audio(chunks, 24000, gap_ms=100)
    assert len(joined) == 2400 * 2 + 2400
    out = ap.export_audio(joined, 24000, tmp_path / "o.wav", "wav")
    assert out.is_file()


@pytest.mark.skipif(not ap.ffmpeg_available(), reason="FFmpeg not available")
def test_export_mp3_and_reload(tmp_path):
    y = make_speech_like(2.0, 24000)
    out = ap.export_audio(y, 24000, tmp_path / "o.mp3", "mp3")
    loaded, sr = ap.load_audio(out)
    assert out.stat().st_size > 1000 and len(loaded) > 24000
