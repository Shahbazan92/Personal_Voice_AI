import pytest

from utils.validators import ValidationError, sniff_audio_format, validate_profile_name, validate_text, validate_upload


def test_rejects_bad_extension():
    with pytest.raises(ValidationError):
        validate_upload("evil.exe", b"MZ" + b"\0" * 100)


def test_rejects_empty_and_fake_audio():
    with pytest.raises(ValidationError):
        validate_upload("a.wav", b"")
    with pytest.raises(ValidationError):
        validate_upload("a.wav", b"this is definitely not audio at all")


def test_accepts_wav_header():
    data = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\0" * 40
    assert validate_upload("a.wav", data) == "wav"


def test_sniff_formats():
    assert sniff_audio_format(b"fLaC" + b"\0" * 12) == "flac"
    assert sniff_audio_format(b"ID3\x04" + b"\0" * 12) == "mp3"
    assert sniff_audio_format(b"\0\0\0\x20ftypM4A " + b"\0" * 4) == "m4a"


def test_profile_name_and_text_rules():
    assert validate_profile_name("  My   voice ") == "My voice"
    with pytest.raises(ValidationError):
        validate_profile_name("a")
    with pytest.raises(ValidationError):
        validate_text("   ")
    with pytest.raises(ValidationError):
        validate_text("x" * 50, max_chars=10)
