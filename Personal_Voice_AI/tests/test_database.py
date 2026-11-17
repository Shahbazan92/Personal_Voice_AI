import pytest

from database.database import DuplicateProfileError


def test_profile_crud(db):
    pid = db.add_profile("Alice", True)
    db.update_profile(pid, reference_audio_path="profiles/profile_001/reference.wav", duration_sec=12.0)
    assert db.get_profile(pid)["reference_audio_path"].endswith("reference.wav")
    db.update_profile(pid, profile_name="Alice 2")
    assert db.list_profiles()[0]["profile_name"] == "Alice 2"
    assert db.count_profiles() == 1
    assert db.delete_profile(pid) and db.count_profiles() == 0


def test_duplicate_names_case_insensitive(db):
    db.add_profile("Alice", True)
    with pytest.raises(DuplicateProfileError):
        db.add_profile("alice", True)


def test_generation_history_and_profile_delete_keeps_history(db):
    pid = db.add_profile("Bob", True)
    gid = db.add_generation(profile_id=pid, profile_name="Bob", input_text="hi", language="en",
                            output_audio_path="outputs/generated/x.wav", model_name="xtts_v2", duration_sec=1.0)
    assert db.count_generations() == 1
    db.delete_profile(pid)
    rec = db.get_generation(gid)
    assert rec is not None and rec["profile_id"] is None and rec["profile_name"] == "Bob"
    assert db.delete_generation(gid) and db.count_generations() == 0


def test_filters(db):
    pid = db.add_profile("C", True)
    for lang in ("en", "es", "es"):
        db.add_generation(profile_id=pid, profile_name="C", input_text="t", language=lang,
                          output_audio_path="o", model_name="m", duration_sec=1)
    assert len(db.list_generations(language="es")) == 2
    assert len(db.list_generations(limit=1)) == 1
