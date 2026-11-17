"""Optional GPU inference server for Personal Voice AI Studio.

Run on a machine with an NVIDIA GPU (from the project root):

    pip install -r server/requirements-server.txt
    export PVAI_API_KEY="a-long-random-secret"
    export PVAI_ACCEPT_COQUI_LICENSE=1      # confirms you accept Coqui's CPML licence
    uvicorn server.inference_server:app --host 0.0.0.0 --port 8000

Put it behind HTTPS (Caddy / nginx / a cloud load balancer) before exposing it to the
internet. The Streamlit app then uses it via Settings → Remote GPU server.
"""
from __future__ import annotations

import hmac
import io
import os
import tempfile
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import soundfile as sf
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response

import config
from core import model_manager
from core.engines.base import EngineError, SynthesisSettings
from core.engines.xtts_engine import XTTSEngine
from core.language_manager import LanguageManager, UnsupportedLanguageError
from core.text_chunker import chunk_text

API_KEY = os.environ.get("PVAI_API_KEY", "")
MAX_REFERENCE_BYTES = 30 * 1024 * 1024
MAX_TEXT = int(os.environ.get("PVAI_MAX_TEXT_CHARS", "3000"))

languages = LanguageManager()
engine = XTTSEngine(device=os.environ.get("PVAI_DEVICE", "auto"), language_codes=languages.codes())
_gpu_lock = threading.Lock()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not API_KEY:
        raise RuntimeError("Set PVAI_API_KEY before starting the server (refusing to run unauthenticated).")
    if os.environ.get("PVAI_ACCEPT_COQUI_LICENSE") == "1":
        model_manager.accept_coqui_license()
    engine.load(print)  # load once at startup
    yield


app = FastAPI(title="Personal Voice AI inference server", lifespan=lifespan)


def require_key(x_api_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_api_key.encode(), API_KEY.encode()):
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/health", dependencies=[Depends(require_key)])
def health() -> dict:
    return {"status": "ok", "model_loaded": engine.is_loaded, "device": engine.device, "languages": languages.codes()}


@app.post("/synthesize", dependencies=[Depends(require_key)])
def synthesize(
    reference: UploadFile = File(...),
    text: str = Form(...),
    language: str = Form(...),
    temperature: float = Form(0.75),
    top_p: float = Form(0.85),
    top_k: int = Form(50),
    repetition_penalty: float = Form(5.0),
    speed: float = Form(1.0),
) -> Response:
    text = text.strip()
    if not text or len(text) > MAX_TEXT:
        raise HTTPException(status_code=400, detail=f"Text must be 1–{MAX_TEXT} characters.")
    try:
        languages.validate(language, engine.supported_language_codes())
    except UnsupportedLanguageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    data = reference.file.read(MAX_REFERENCE_BYTES + 1)
    if not data or len(data) > MAX_REFERENCE_BYTES:
        raise HTTPException(status_code=413, detail="Reference audio is empty or too large.")

    settings = SynthesisSettings(
        temperature=min(max(temperature, 0.1), 1.5), top_p=min(max(top_p, 0.1), 1.0),
        top_k=min(max(top_k, 1), 100), repetition_penalty=min(max(repetition_penalty, 1.0), 20.0),
        speed=min(max(speed, 0.5), 2.0),
    )
    chunks = chunk_text(text, max(int(languages.char_limit(language) * 0.9), 20))
    with tempfile.TemporaryDirectory() as tmp:
        ref_path = Path(tmp) / "reference.wav"  # content is sniffed by soundfile/ffmpeg, name is irrelevant
        ref_path.write_bytes(data)
        try:
            with _gpu_lock:
                wav, sr = engine.synthesize(chunks, ref_path, language, settings)
        except model_manager.InsufficientMemoryError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except EngineError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    buf = io.BytesIO()
    sf.write(buf, wav, sr, format="WAV", subtype="PCM_16")
    return Response(content=buf.getvalue(), media_type="audio/wav")
