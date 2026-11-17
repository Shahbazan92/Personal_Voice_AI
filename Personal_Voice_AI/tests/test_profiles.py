import pytest

from core.profile_service import ConsentRequiredError
from database.database import DuplicateProfileError
from utils.validators import ValidationError


def test_create_requires_consent(profiles, speech_wav):
    with pytest.raises(ConsentRequiredError):
        profiles.create("Me", "me.wav", speech_wav, consent=False)
    assert profiles.list() == []


def test_create_stores_files_and_json(profiles, storage, speech_wav):
    pid, report = profiles.create("My voice", "me.wav", speech_wav, consent=True)
    assert report.ok
    assert storage.exists("profiles/profile_001/reference.wav")
    assert storage.exists("profiles/profile_001/original.wav")
    assert storage.exists("profiles/profile_001/profile.json")
    assert profiles.reference_path(pid).is_file()


def test_invalid_upload_leaves_no_trace(profiles, storage, short_wav):
    with pytest.raises(Exception):
        profiles.create("Short", "s.wav", short_wav, consent=True)
    assert profiles.list() == [] and not storage.exists("profiles/profile_001/reference.wav")


def test_bad_file_type_rejected(profiles):
    with pytest.raises(ValidationError):
        profiles.create("Bad", "x.txt", b"hello", consent=True)


def test_duplicate_name(profiles, speech_wav):
    profiles.create("Dup", "a.wav", speech_wav, True)
    with pytest.raises(DuplicateProfileError):
        profiles.create("dup", "a.wav", speech_wav, True)


def test_rename_replace_delete_only_touches_own_folder(profiles, storage, speech_wav):
    a, _ = profiles.create("Aa", "a.wav", speech_wav, True)
    b, _ = profiles.create("Bb", "b.wav", speech_wav, True)
    profiles.rename(a, "A renamed")
    profiles.replace_recording(a, "new.wav", speech_wav)
    profiles.delete(a)
    assert not storage.exists("profiles/profile_001/reference.wav")
    assert storage.exists("profiles/profile_002/reference.wav")
    assert [p["id"] for p in profiles.list()] == [b]
