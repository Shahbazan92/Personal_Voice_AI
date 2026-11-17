"""Client for a separate GPU inference server (see ``server/inference_server.py``).

Use this when the host running the Streamlit UI (e.g. Streamlit Community Cloud) is
too small to run XTTS-v2. NOTE: the processed reference recording is uploaded to
your server for every request, so only use a server you control, over HTTPS.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Callable

import numpy as np
import requests
import soundfile as sf

from core.engines.base import EngineError, ProgressCallback, SynthesisSettings, TTSEngine
from core.language_manager import DEFAULT_LANGUAGES


class RemoteGPUEngine(TTSEngine):
    name = "remote_gpu"
    label = "Remote GPU server (XTTS-v2)"
    description = "Runs XTTS-v2 on your own GPU server through a secured HTTP API."
    runs_locally = False

    def __init__(self, base_url: str, api_key: str = "", timeout: int = 900) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.timeout = timeout
        self._codes = [lang.code for lang in DEFAULT_LANGUAGES]
        self._connected = False

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key} if self.api_key else {}

    def is_available(self) -> tuple[bool, str]:
        if not self.base_url:
            return False, "No remote server URL configured (Settings → Remote GPU server)."
        if not self.base_url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            return False, "For security the remote URL must use https:// (http:// is only allowed for localhost)."
        return True, ""

    def supported_language_codes(self) -> list[str]:
        return list(self._codes)

    @property
    def is_loaded(self) -> bool:
        return self._connected

    def load(self, progress: Callable[[str], None] | None = None) -> None:
        ok, reason = self.is_available()
        if not ok:
            raise EngineError(reason)
        try:
            resp = requests.get(f"{self.base_url}/health", headers=self._headers(), timeout=30)
        except requests.RequestException as exc:
            raise EngineError(f"Cannot reach the remote server: {exc}") from exc
        if resp.status_code == 401:
            raise EngineError("The remote server rejected the API key.")
        if resp.status_code != 200:
            raise EngineError(f"Remote server health check failed (HTTP {resp.status_code}).")
        info = resp.json()
        if not info.get("model_loaded", False):
            raise EngineError("The remote server is up but its model is not loaded yet. Try again in a minute.")
        self._codes = info.get("languages") or self._codes
        self._connected = True

    def synthesize(
        self,
        chunks: list[str],
        reference_path: Path,
        language: str,
        settings: SynthesisSettings,
        progress: ProgressCallback | None = None,
    ) -> tuple[np.ndarray, int]:
        self.load()
        if progress:
            progress(0, 1, "Waiting for the remote GPU server…")
        data = {
            "text": " ".join(chunks),
            "language": language,
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "top_k": settings.top_k,
            "repetition_penalty": settings.repetition_penalty,
            "speed": settings.speed,
        }
        try:
            with open(reference_path, "rb") as fh:
                resp = requests.post(
                    f"{self.base_url}/synthesize",
                    headers=self._headers(),
                    data=data,
                    files={"reference": (Path(reference_path).name, fh, "audio/wav")},
                    timeout=self.timeout,
                )
        except requests.RequestException as exc:
            raise EngineError(f"Remote request failed: {exc}") from exc
        if resp.status_code != 200:
            try:
                detail = resp.json().get("detail", resp.text)
            except ValueError:
                detail = resp.text
            raise EngineError(f"Remote server error {resp.status_code}: {str(detail)[:300]}")
        try:
            wav, sr = sf.read(io.BytesIO(resp.content), dtype="float32", always_2d=False)
        except Exception as exc:  # noqa: BLE001
            raise EngineError(f"The remote server returned invalid audio: {exc}") from exc
        if progress:
            progress(1, 1, "Finalising audio…")
        return np.asarray(wav, dtype=np.float32), int(sr)
