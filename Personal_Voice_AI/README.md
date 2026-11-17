# 🎙️ Personal Voice AI Studio

Record your voice once → pick a language → type text → get speech in **your own voice**.
Built with Streamlit + Coqui **XTTS-v2** (real model inference, no simulated output).

> **Read this first (honest status).** The code was written and its logic tests were run in a sandbox without
> internet, so I could **not** install PyTorch/Coqui TTS there or run the real model, and the Streamlit UI was not
> launched. The model-independent logic (validation, storage, database, chunking, audio processing, profile and
> generation orchestration) passed 42 tests using stand-in audio libraries. The first real run on your machine
> is the true integration test; see *Troubleshooting* if a version conflict appears.

---

## 1. Features

* Upload (WAV, MP3, M4A, FLAC) or **record in the browser**; validation (type, size, real content sniffing,
  duration, clipping, noise estimate), DC removal, optional noise reduction, silence trim, resample, loudness
  normalisation. The **original upload is kept unchanged**; a processed `reference.wav` is created.
* Multiple voice profiles (SQLite + `profile.json` per profile), rename / replace / delete, **consent required**.
* Cross-language generation with XTTS-v2 (17 documented languages). **Urdu is not officially supported and is
  never silently replaced by Hindi/Arabic.** The language list is configurable (`languages.json`).
* Long text is split into sentence-aware chunks; speaker latents are computed **once** and re-used for every chunk
  to keep the voice consistent.
* Audio library with history, playback, WAV/MP3 download, delete.
* Pages: Dashboard, Voice Profiles, Generate Speech, Audio Library, Settings, About. Light/dark follows the
  system or `⋮ → Settings → Theme`.
* Pluggable engines: local XTTS-v2, **Remote GPU server** (included), VoxCPM2 **interface only** (see §10).
* Storage abstraction (`core/storage.py`) so persistent cloud storage can replace local disk later.

## 2. Project structure

```
Personal_Voice_AI/
├── app.py                      Streamlit entry point
├── config.py                   paths, limits, environment variables
├── requirements.txt            light UI deps (what Streamlit Cloud installs)
├── requirements-xtts.txt       + PyTorch / Coqui TTS (local or GPU server)
├── packages.txt                apt packages for Streamlit Cloud (ffmpeg, libsndfile1)
├── runtime.txt / .python-version   Python 3.11 (see §6 note)
├── .streamlit/config.toml, secrets.toml.example
├── core/
│   ├── model_manager.py        dependency checks, device, download/load, OOM handling
│   ├── voice_cloner.py         engine registry / factory
│   ├── engines/                base.py, xtts_engine.py, remote_engine.py, voxcpm_engine.py
│   ├── audio_processor.py      load/validate/clean/convert/export
│   ├── speech_generator.py     validate → chunk → synthesise → save → history
│   ├── profile_service.py      profile lifecycle
│   ├── language_manager.py     language registry
│   ├── text_chunker.py, storage.py, settings.py
├── database/database.py        SQLite
├── ui/                         one module per page
├── server/inference_server.py  optional FastAPI GPU server
├── utils/                      validators.py, helpers.py
├── tests/                      pytest suite
├── profiles/ outputs/ data/ models/   runtime data (git-ignored)
└── assets/logo.png
```

## 3. Run locally on Windows (step by step)

1. Install **Python 3.11** from python.org (tick *Add python.exe to PATH*). Python 3.10–3.12 should also work.
2. Open **PowerShell** in the project folder:
   ```powershell
   py -3.11 -m venv .venv
   .venv\Scripts\Activate.ps1        # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   python -m pip install --upgrade pip
   ```
3. Install **PyTorch first** (choose one):
   ```powershell
   # CPU only (works everywhere, slow generation)
   pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
   # NVIDIA GPU (CUDA 12.4)
   pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu124
   ```
4. Install the rest:
   ```powershell
   pip install -r requirements-xtts.txt
   ```
   Japanese / Korean / Chinese also need: `pip install "coqui-tts[ja,ko,zh]"`.
5. Start:
   ```powershell
   streamlit run app.py
   ```
6. First generation: open **Generate Speech** → accept the Coqui licence (CPML, non-commercial) → **Download & load
   model** (≈1.8 GB, once, stored in `models/`). The app starts fine without the model and shows these steps.

FFmpeg is bundled through `imageio-ffmpeg`; a system FFmpeg is used if present.
RAM guide (estimate): CPU 6 GB+ free recommended; GPU 6 GB+ VRAM.

## 4. Testing

```powershell
pip install pytest
pytest                                   # fast tests (no model needed)
$env:RUN_MODEL_TESTS="1"; pytest -m model   # real XTTS-v2 test (downloads the model)
```
Covers: upload validation, audio processing, profile create/delete, language selection, database, storage safety,
orchestration/saving (with a test-only fake engine), app start-up on every page, and real model loading +
generation (opt-in).

## 5. Where it can run — be realistic

| Host | XTTS-v2 inside the app? |
|---|---|
| Your Windows/Linux PC | ✅ (CPU slow, GPU fast) |
| Your own GPU server | ✅ best option |
| **Streamlit Community Cloud** | ⚠️ **Unlikely.** Free resources are roughly 2–3 GB RAM, no GPU (check current docs); the model alone is ≈1.8 GB and CPU inference needs more. |

So the repository defaults to a **two-part architecture for Streamlit Cloud**: the Streamlit UI (light
`requirements.txt`) + a **Remote GPU server** running XTTS-v2 (`server/inference_server.py`). The UI auto-selects
the remote engine when PyTorch/TTS are not installed and a server URL is configured. Nothing is faked.

## 6. Deploy to Streamlit Community Cloud

1. **GitHub account:** https://github.com/signup
2. **New repository:** GitHub → `+` → *New repository* → name `Personal_Voice_AI` → *Private* is recommended →
   *Create*.
3. **Upload files:** unzip this project; on the repo page choose *Add file → Upload files*, drag **everything
   inside** the `Personal_Voice_AI` folder (so `app.py` is at the repo root), then *Commit changes*.
   (Or: `git init && git add . && git commit -m init && git remote add origin <url> && git push -u origin main`.)
   Check that **no recordings / `secrets.toml`** are included (`.gitignore` already excludes them).
4. Open **https://share.streamlit.io/** → sign in with GitHub → **Create app** → pick your repository, branch
   `main`, **Main file path: `app.py`**.
5. **Advanced settings:** choose **Python 3.11**. *Note:* Streamlit Community Cloud selects Python here;
   `runtime.txt` is included for other platforms and is not relied upon.
6. **Secrets** (Advanced settings → Secrets) if you use a remote GPU server:
   ```toml
   remote_url = "https://gpu.example.com"
   remote_api_key = "your-long-random-key"
   ```
7. Click **Deploy**. The first build installs `requirements.txt` and `packages.txt`.

**Storage on Streamlit Cloud is temporary.** Profiles, generated audio and the SQLite file live on a container disk
that is wiped when the app restarts or redeploys. Do not rely on it; download what you need. For persistence, implement
`StorageBackend` (S3 / Supabase / GCS, `core/storage.py`) and an external database, then return them in
`ui/services.py`. Also remember the app is on shared infrastructure: avoid uploading sensitive recordings unless you
accept that. Never commit recordings to GitHub.

*Trying XTTS directly on Cloud anyway:* put the contents of `requirements-xtts.txt` into `requirements.txt`, and add
as its first line `--extra-index-url https://download.pytorch.org/whl/cpu` to avoid the multi-GB CUDA build. Expect
memory-limit crashes; the app reports `InsufficientMemory` messages instead of hiding them.

## 7. Remote GPU server

On a machine with an NVIDIA GPU (Linux):
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu124
pip install -r server/requirements-server.txt
export PVAI_API_KEY="$(openssl rand -hex 32)"
export PVAI_ACCEPT_COQUI_LICENSE=1       # you confirm you accept Coqui's CPML licence
uvicorn server.inference_server:app --host 127.0.0.1 --port 8000
```
Put HTTPS in front (Caddy/nginx/cloud load balancer). The client refuses non-HTTPS URLs except localhost, the server
refuses to start without an API key, and the model loads once at start-up. **Privacy:** every request uploads the
processed reference voice to *your* server.

## 8. Settings / environment variables

`PVAI_DATA_DIR` (data root) · `PVAI_MAX_TEXT_CHARS` (default 3000) · `PVAI_MAX_UPLOAD_MB` (50) ·
`PVAI_REMOTE_URL`, `PVAI_REMOTE_API_KEY` · `TTS_HOME` (model folder). The API key is never written to disk.

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `pip` dependency conflict | Use Python 3.11; install PyTorch first (§3); then `pip install -r requirements-xtts.txt`. If a pin conflicts, run `pip install --upgrade coqui-tts` and keep `torch/torchaudio` below 2.9. Report the exact error with `pip freeze`. |
| `No module named TTS` / app says engine not ready | `pip install -r requirements-xtts.txt` inside the activated venv. |
| Errors about **TorchCodec** / `torchaudio.load` | You have torchaudio ≥ 2.9: `pip install "torch<2.9" "torchaudio<2.9"`. |
| Model download fails / stalls | Check disk (≥ 4 GB free) and internet; delete the partial folder in `models/` and retry; accept the licence. |
| Japanese/Korean/Chinese fails | `pip install "coqui-tts[ja,ko,zh]"` (some need build tools on Windows). |
| Out-of-memory | Close apps, shorten text, use CPU if VRAM is small, or use the Remote GPU engine. |
| M4A/MP3 won't load | Ensure `imageio-ffmpeg` installed or install FFmpeg (`winget install ffmpeg`). |
| Microphone button missing | Needs Streamlit ≥ 1.40 and HTTPS or `localhost`; allow the mic in the browser. |
| Cloud app crashes at start | See build logs; the light `requirements.txt` should install; check `packages.txt`; use Python 3.11. |
| Voice sounds off | Use 15–30 s of clean, single-speaker speech; enable noise reduction; lower temperature. |

## 10. Known limitations & extending

* Cross-language output keeps your timbre but accent/prosody are approximate; results vary by recording.
* XTTS-v2 can hallucinate on very short or very long chunks; numbers/abbreviations are best written out in words.
* XTTS-v2 licence is **non-commercial** (CPML). Check it before any commercial use.
* CPU generation is slow (often slower than real time).
* **VoxCPM2** is *not* integrated: its real inference API must be checked against the official repo
  (https://github.com/OpenBMB/VoxCPM). Follow the steps in `core/engines/voxcpm_engine.py`; the registry, UI,
  history and storage already support extra engines.
* No translation module is included (TTS does not translate); add one as a separate module if needed.

## 11. Responsible use

Clone only your own voice or voices you have explicit permission to use. Generated audio is AI-generated; never use
it to impersonate others, deceive, or commit fraud. The app asks for consent before creating a profile.
