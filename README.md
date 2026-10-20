# IncuBrix Engineering Assessment PS3: Script and Voiceover to B-Roll Video Engine

A modular, production-ready web application and REST API that converts either a plain-text script (`script.txt`) or a voiceover recording (`voice.mp3` / `voice.wav`) into a synchronized 720p MP4 B-roll video complete with burned-in/muxed SubRip captions (`captions.srt`), scene timing metadata (`timeline.json`), commercial license provenance (`manifest.json`), and structured per-job execution logs (`logs.txt`).

---

## 1. Architecture Overview

```text
+-------------------+       POST /generate        +------------------------+
|  React + Vite UI  | --------------------------> |   FastAPI Controller   |
|  (Dark Theme SPA) | <-------------------------- |   (Async Background)   |
+-------------------+    GET /status & /result    +-----------+------------+
                                                              |
                                                              v
                                            +----------------------------------+
                                            |     VideoGenerationPipeline      |
                                            +-----------------+----------------+
                                                              |
        +-----------------------+-----------------------------+-----------------------------+
        |                       |                             |                             |
        v                       v                             v                             v
+---------------+     +-------------------+         +-------------------+         +-------------------+
| AudioService  |     |   SceneService    |         |   BRollService    |         |   VideoService    |
| - Whisper STT |     | - Paragraph/Pause |         | - Pexels Primary  |         | - FFmpeg Scale/Pad|
| - gTTS / Wave |     |   Segmentation    |         | - Pixabay Fallback|         | - SRT Subtitles   |
| - ffprobe     |     | - Keyword Ranking |         | - Local Fallback  |         | - AAC Audio Mux   |
+---------------+     +-------------------+         +-------------------+         +-------------------+
                                                              |
                                                              v
                                            +----------------------------------+
                                            |         jobs/{job_id}/           |
                                            |  - video.mp4                     |
                                            |  - captions.srt                  |
                                            |  - timeline.json                 |
                                            |  - manifest.json                 |
                                            |  - logs.txt                      |
                                            +----------------------------------+
```

## 2. Folder Structure

* backend/ — FastAPI application, SQLite repository, Pydantic schemas, and modular domain services.
* frontend/ — React 18 + Vite dark-theme responsive client.
* docker/ — Production Dockerfiles for backend and frontend + Nginx proxy config.
* tests/ — Pytest unit and integration suite covering upload, Whisper transcription, scene detection, B-roll fallback, and FFmpeg rendering.
* assets/ — Local fallback media generator (ensure_fallback.py).
* jobs/ — Output directory storing per-job artifacts under jobs/{job_id}/.

## 3. Installation & Running Locally

### Prerequisites

* Python 3.11+
* Node.js 20+
* FFmpeg (ffmpeg and ffprobe available on system PATH)

### Step 1: Configure Environment

```bash
cp .env.example .env
# Edit .env and add your PEXELS_API_KEY and PIXABAY_API_KEY
```

### Step 2: Start Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m assets.ensure_fallback
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 3: Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

## 4. Running with Docker

Build and start both the FastAPI backend and React/Nginx frontend using a single command:

```bash
cp .env.example .env
docker compose up --build
```

* Web UI: http://localhost:3000
* REST API & Swagger Docs: http://localhost:8000/docs

## 5. API Examples

### Submit a Script (script.txt)

```bash
curl -X POST http://localhost:8000/generate \
  -F "script=@script.txt"
```

Response:

```json
{
  "job_id": "4f8a2b1c-9d7e-4c3a-8f12-3b5e9a1d7c4e",
  "status": "queued",
  "message": "Script job queued for processing."
}
```

### Submit a Voice Recording (voice.mp3)

```bash
curl -X POST http://localhost:8000/generate \
  -F "audio=@voice.mp3"
```

### Poll Job Status

```bash
curl http://localhost:8000/status/4f8a2b1c-9d7e-4c3a-8f12-3b5e9a1d7c4e
```

### Retrieve Results & Download Artifacts

```bash
# JSON overview with inline timeline & manifest
curl http://localhost:8000/result/4f8a2b1c-9d7e-4c3a-8f12-3b5e9a1d7c4e

# Direct file downloads
curl -OJ "http://localhost:8000/result/4f8a2b1c-9d7e-4c3a-8f12-3b5e9a1d7c4e?file=video"
curl -OJ "http://localhost:8000/result/4f8a2b1c-9d7e-4c3a-8f12-3b5e9a1d7c4e?file=captions"
curl -OJ "http://localhost:8000/result/4f8a2b1c-9d7e-4c3a-8f12-3b5e9a1d7c4e?file=timeline"
curl -OJ "http://localhost:8000/result/4f8a2b1c-9d7e-4c3a-8f12-3b5e9a1d7c4e?file=manifest"
```

## 6. Running Automated Tests

```bash
pytest -v
```

## 7. UI Preview & Screenshots

* Dashboard Split View: Left pane provides one-click switching between Script Upload (.txt or inline editor) and Audio Upload (.mp3/.wav), live progress bar, and step telemetry.
* Preview & Inspector Pane: Right pane renders an HTML5 video player, direct download buttons for .mp4, .srt, timeline.json, manifest.json, and a full .zip bundle, plus interactive tables for scene timing and license attribution.
