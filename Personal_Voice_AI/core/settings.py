"""User-editable application settings, persisted as JSON.

Secrets (the remote API key) are intentionally NOT stored here.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass
class AppSettings:
    engine: str = "auto"              # auto | xtts_v2 | remote_gpu | voxcpm2
    device: str = "auto"              # auto | cpu | cuda
    output_format: str = "wav"        # wav | mp3
    mp3_bitrate: str = "192k"
    noise_reduction_default: bool = False
    temperature: float = 0.75
    top_p: float = 0.85
    top_k: int = 50
    repetition_penalty: float = 5.0
    speed: float = 1.0
    coqui_license_accepted: bool = False
    remote_url: str = ""

    @classmethod
    def load(cls, path: Path) -> "AppSettings":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        tmp.replace(path)
