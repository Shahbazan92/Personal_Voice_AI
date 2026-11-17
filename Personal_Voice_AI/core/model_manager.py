"""Dependency checks, device detection, model download and loading for XTTS-v2.

Nothing heavy (torch, TTS) is imported at module import time, so the app starts
and can show setup instructions even when the model stack is not installed.
"""
from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import config


class DependencyMissingError(RuntimeError):
    pass


class ModelLoadError(RuntimeError):
    pass


class InsufficientMemoryError(RuntimeError):
    pass


@dataclass
class ModelStatus:
    deps_installed: bool
    missing: list[str] = field(default_factory=list)
    model_downloaded: bool = False
    cuda_available: bool = False
    available_ram_gb: float | None = None
    total_ram_gb: float | None = None


def missing_dependencies() -> list[str]:
    """Names of pip packages required for local XTTS-v2 that are not installed."""
    needed = {"torch": "torch", "torchaudio": "torchaudio", "TTS": "coqui-tts"}
    return [pip for mod, pip in needed.items() if importlib.util.find_spec(mod) is None]


def cuda_available() -> bool:
    if importlib.util.find_spec("torch") is None:
        return False
    import torch

    return bool(torch.cuda.is_available())


def detect_device(preference: str = "auto") -> str:
    """Resolve 'auto' / 'cpu' / 'cuda' into a usable torch device string."""
    if preference == "cpu":
        return "cpu"
    if cuda_available():
        return "cuda"
    if preference == "cuda":
        raise ModelLoadError("CUDA was requested but no NVIDIA GPU / CUDA-enabled PyTorch was found.")
    return "cpu"


def memory_info() -> tuple[float | None, float | None]:
    """(available_gb, total_gb) or (None, None) when psutil is missing."""
    try:
        import psutil

        vm = psutil.virtual_memory()
        return vm.available / 1024**3, vm.total / 1024**3
    except Exception:  # noqa: BLE001
        return None, None


def _candidate_model_roots() -> list[Path]:
    roots = [Path(os.environ.get("TTS_HOME", config.MODELS_DIR)).expanduser()]
    roots.append(Path.home() / ".local" / "share" / "tts")
    if os.environ.get("LOCALAPPDATA"):
        roots.append(Path(os.environ["LOCALAPPDATA"]) / "tts")
    return roots


def is_model_downloaded() -> bool:
    """True if an XTTS-v2 checkpoint folder with ``model.pth`` exists in a known cache."""
    for root in _candidate_model_roots():
        if root.is_dir():
            for model_file in root.rglob("model.pth"):
                if "xtts_v2" in str(model_file).lower():
                    return True
    return False


def get_status() -> ModelStatus:
    missing = missing_dependencies()
    available, total = memory_info()
    return ModelStatus(
        deps_installed=not missing,
        missing=missing,
        model_downloaded=is_model_downloaded(),
        cuda_available=cuda_available(),
        available_ram_gb=available,
        total_ram_gb=total,
    )


def accept_coqui_license() -> None:
    """Coqui asks for CPML acceptance on first download; this answers it non-interactively.

    Only call this after the user has explicitly accepted the licence in the UI.
    """
    os.environ["COQUI_TOS_AGREED"] = "1"


def _is_oom(exc: BaseException) -> bool:
    text = str(exc).lower()
    return isinstance(exc, MemoryError) or "out of memory" in text or "cuda error: out of memory" in text \
        or "not enough memory" in text or "defaultcpuallocator" in text


def load_xtts(device: str = "auto", progress: Callable[[str], None] | None = None):
    """Download (first run only) and load XTTS-v2. Returns a ``TTS`` instance on ``device``."""
    say = progress or (lambda _msg: None)
    missing = missing_dependencies()
    if missing:
        raise DependencyMissingError(
            "Missing packages: " + ", ".join(missing) + ". Install them with: pip install -r requirements-xtts.txt"
        )
    resolved = detect_device(device)
    try:
        from TTS.api import TTS
    except Exception as exc:  # noqa: BLE001 - import errors come in many forms
        raise DependencyMissingError(
            f"The Coqui TTS package could not be imported: {exc}. Check the README troubleshooting section."
        ) from exc

    say("Downloading model (first run only, ~1.8 GB)…" if not is_model_downloaded() else "Loading model into memory…")
    try:
        tts = TTS(config.XTTS_MODEL_NAME)
        say(f"Moving model to {resolved.upper()}…")
        tts.to(resolved)
    except Exception as exc:  # noqa: BLE001
        if _is_oom(exc):
            _free_cuda_cache()
            raise InsufficientMemoryError(
                "Not enough memory to load XTTS-v2. Close other applications, use a machine with more RAM/VRAM, "
                "or switch to the remote GPU engine in Settings."
            ) from exc
        raise ModelLoadError(f"Could not load XTTS-v2: {exc}") from exc
    say("Model ready.")
    return tts


def _free_cuda_cache() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001
        pass


free_cuda_cache = _free_cuda_cache
is_oom_error = _is_oom
