"""Engine registry / factory. Add new engines to ``ENGINES`` to make them selectable."""
from __future__ import annotations

from dataclasses import dataclass

from core import model_manager
from core.engines.base import EngineError, TTSEngine
from core.engines.remote_engine import RemoteGPUEngine
from core.engines.voxcpm_engine import VoxCPM2Engine
from core.engines.xtts_engine import XTTSEngine


@dataclass(frozen=True)
class EngineInfo:
    name: str
    label: str
    description: str


ENGINES: dict[str, EngineInfo] = {
    XTTSEngine.name: EngineInfo(XTTSEngine.name, XTTSEngine.label, XTTSEngine.description),
    RemoteGPUEngine.name: EngineInfo(RemoteGPUEngine.name, RemoteGPUEngine.label, RemoteGPUEngine.description),
    VoxCPM2Engine.name: EngineInfo(VoxCPM2Engine.name, VoxCPM2Engine.label, VoxCPM2Engine.description),
}


def resolve_engine_name(choice: str, remote_url: str = "") -> str:
    """Turn the 'auto' setting into a concrete engine name.

    auto → local XTTS-v2 if its packages are installed, else the remote server if a URL is set,
    else local XTTS-v2 (the UI then shows install instructions).
    """
    if choice != "auto":
        if choice not in ENGINES:
            raise EngineError(f"Unknown engine '{choice}'.")
        return choice
    if not model_manager.missing_dependencies():
        return XTTSEngine.name
    if remote_url:
        return RemoteGPUEngine.name
    return XTTSEngine.name


def build_engine(name: str, device: str = "auto", remote_url: str = "", remote_key: str = "",
                 language_codes: list[str] | None = None) -> TTSEngine:
    if name == XTTSEngine.name:
        return XTTSEngine(device=device, language_codes=language_codes)
    if name == RemoteGPUEngine.name:
        return RemoteGPUEngine(remote_url, remote_key)
    if name == VoxCPM2Engine.name:
        return VoxCPM2Engine()
    raise EngineError(f"Unknown engine '{name}'.")
