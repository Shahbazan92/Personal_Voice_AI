"""Storage abstraction.

The rest of the app only deals in *keys* (POSIX-style relative paths such as
``profiles/profile_001/reference.wav``). ``LocalStorage`` maps keys to a folder on
disk. To use persistent cloud storage later (S3, Supabase, GCS ...), implement
``StorageBackend`` and return it from ``ui/services.py``; nothing else changes.
"""
from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from utils.helpers import is_relative_to


class StorageError(RuntimeError):
    pass


class StorageBackend(ABC):
    @abstractmethod
    def put_file(self, source: Path, key: str) -> str: ...

    @abstractmethod
    def put_bytes(self, data: bytes, key: str) -> str: ...

    @abstractmethod
    def local_path(self, key: str) -> Path:
        """Return a readable local path for ``key`` (cloud backends download to a cache)."""

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> bool: ...

    @abstractmethod
    def delete_prefix(self, prefix: str) -> bool:
        """Delete a whole 'folder'. Must refuse to delete the storage root."""


class LocalStorage(StorageBackend):
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        if not key or key.startswith(("/", "\\")) or ":" in key.split("/")[0]:
            raise StorageError(f"Invalid storage key: {key!r}")
        path = (self.root / key).resolve()
        if not is_relative_to(path, self.root) or path == self.root:
            raise StorageError(f"Storage key escapes the storage root: {key!r}")
        return path

    def put_file(self, source: Path, key: str) -> str:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return key

    def put_bytes(self, data: bytes, key: str) -> str:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return key

    def local_path(self, key: str) -> Path:
        return self._resolve(key)

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).is_file()
        except StorageError:
            return False

    def delete(self, key: str) -> bool:
        path = self._resolve(key)
        if path.is_file():
            path.unlink()
            return True
        return False

    def delete_prefix(self, prefix: str) -> bool:
        path = self._resolve(prefix.rstrip("/"))
        if path.is_dir():
            shutil.rmtree(path)
            return True
        return False
