# External Libraries, APIs & Media Sources (`SOURCES.md`)

## 1. Stock Media Providers & Commercial Licenses

| Provider | API Endpoint | License Terms | Attribution Requirement |
|---|---|---|---|
| **Pexels API** (Primary) | `https://api.pexels.com/videos/search` | Pexels License — Free for commercial and non-commercial use | Not required (author recorded in `manifest.json`) |
| **Pixabay API** (Fallback) | `https://pixabay.com/api/videos/` | Pixabay Content License — Free for commercial and non-commercial use | Not required (author recorded in `manifest.json`) |
| **Local FFmpeg Fallback** | `assets/fallback_broll.mp4` | CC0 1.0 Universal (Self-generated synthetic canvas) | None |

---

## 2. Backend & Media Processing Libraries
- **FastAPI (`0.115.0`)** — MIT License — High-performance async REST framework.
- **Uvicorn (`0.30.6`)** — BSD-3-Clause — ASGI web server.
- **Pydantic & Pydantic-Settings (`2.9.2` / `2.5.2`)** — MIT License — Strict schema validation and `.env` configuration management.
- **faster-whisper (`1.1.0`)** — MIT License — CTranslate2-based Whisper reimplementation for speech recognition (faster, lighter than PyTorch Whisper).
- **Python `srt` (`3.5.3`)** — MIT License — SubRip (`.srt`) subtitle composition and parsing.
- **HTTPX (`0.27.2`)** — BSD-3-Clause — Async HTTP client with timeout control for Pexels and Pixabay API calls.
- **gTTS (`2.5.3`)** — MIT License — Text-to-speech synthesis for plain-text script inputs.
- **FFmpeg / FFprobe** — LGPL v2.1+ / GPL v2+ — Audio/video probing, scaling, padding, concatenation, and MP4 encoding.
- **SQLite3** — Public Domain — Embedded relational database for job state persistence.
- **Pytest & Pytest-Asyncio (`8.3.3` / `0.24.0`)** — MIT / Apache-2.0 — Automated testing framework.

---

## 3. Frontend Libraries
- **React & React DOM (`18.3.1`)** — MIT License — Component UI library.
- **Vite (`5.4.6`)** — MIT License — Frontend build tool and dev server.
