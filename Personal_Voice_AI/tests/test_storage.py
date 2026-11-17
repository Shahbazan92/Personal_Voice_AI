import pytest

from core.storage import StorageError


def test_put_read_delete(storage, tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("hi")
    storage.put_file(src, "profiles/profile_001/a.txt")
    assert storage.exists("profiles/profile_001/a.txt")
    assert storage.delete("profiles/profile_001/a.txt")
    assert not storage.exists("profiles/profile_001/a.txt")


@pytest.mark.parametrize("key", ["../escape.txt", "/etc/passwd", "a/../../b", ""])
def test_rejects_unsafe_keys(storage, key):
    with pytest.raises(StorageError):
        storage.put_bytes(b"x", key)


def test_cannot_delete_root(storage):
    with pytest.raises(StorageError):
        storage.delete_prefix("")
    with pytest.raises(StorageError):
        storage.delete_prefix("a/..")


def test_delete_prefix_only_removes_that_folder(storage):
    storage.put_bytes(b"1", "profiles/profile_001/x.wav")
    storage.put_bytes(b"2", "profiles/profile_002/x.wav")
    storage.delete_prefix("profiles/profile_001")
    assert not storage.exists("profiles/profile_001/x.wav")
    assert storage.exists("profiles/profile_002/x.wav")
