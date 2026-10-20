# Engineering Report: Script and Voiceover to B-Roll Video Engine

## 1. Design Decisions

### Clean Architecture & Service Isolation
The backend separates HTTP transport (`backend/main.py`), persistence (`backend/database.py`), data validation (`backend/schemas.py`), and media processing (`backend/services/`). Each service has a single responsibility:
- **`AudioService`**: Wraps faster-whisper (CTranslate2) for voiceover transcription and `gTTS`/FFmpeg synthesis for plain-text scripts, ensuring both input modes produce frame-accurate audio timing probed via `ffprobe`.
- **`SceneService`**: Combines structural breaks (paragraphs, sentence boundaries) with acoustic pause detection (`pause_threshold_seconds = 0.8s`) and a maximum scene duration cap (`10.0s`) so visual pacing stays dynamic.
- **`BRollService`**: Implements a 4-tier resilience cascade:
  1. Compound keyword search on Pexels API (`"kw1 kw2"`).
  2. Individual keyword fallback on Pexels API.
  3. Secondary provider failover to Pixabay Videos API.
  4. Guaranteed local commercial-safe fallback clip (`assets/fallback_broll.mp4`) so jobs never fail due to third-party rate limits or zero-hit queries.
- **`VideoService`**: Normalizes heterogeneous stock clips (varying resolutions, aspect ratios, and frame rates) to 1280x720 @ 30fps `yuv420p` using FFmpeg `scale` + `pad` filters and `-stream_loop -1` before concatenation and subtitle/audio muxing.

### Asynchronous Job Execution & SQLite Persistence
Video rendering and Whisper transcription are CPU/IO-intensive. `POST /generate` validates input headers synchronously (failing fast with HTTP 400 on unsupported extensions or oversized/excessively long audio) before dispatching the heavy pipeline to an asynchronous background task tracked in SQLite.

---

## 2. System Workflow
1. **Ingestion & Validation**: Verify file extension (`.txt`, `.mp3`, `.wav`), size limit, and audio duration via `ffprobe`.
2. **Speech-to-Text / TTS Alignment**:
   - Audio inputs are transcribed locally via faster-whisper (`base` model by default, CTranslate2 backend).
   - Script inputs are segmented into scenes, synthesized into speech per scene, and concatenated so every scene's `start_time` and `end_time` matches the spoken narration.
3. **Scene Detection & Keyword Extraction**: Scenes are bounded by sentence punctuation and pauses; stopword-filtered frequency and token-length heuristics select the top visual keywords.
4. **Stock Media Retrieval & Manifest Logging**: Pexels and Pixabay APIs are queried for landscape MP4s closest to the scene duration. Every downloaded clip is recorded in `manifest.json` with provider, original URL, license, author, and UTC download timestamp.
5. **Subtitle Composition**: Python's `srt` library builds standards-compliant `captions.srt`.
6. **FFmpeg Rendering**: Each B-roll clip is looped/trimmed to exact scene duration, scaled/padded to 720p, concatenated, and combined with the narration track and subtitles into `jobs/{job_id}/video.mp4`.

---

## 3. Limitations
- **Keyword Context**: Lexical keyword extraction selects salient nouns/verbs from the transcript but does not perform deep visual metaphor rewriting (e.g., translating abstract idioms into concrete visual descriptions).
- **CPU Whisper & x264 Latency**: Running faster-whisper and FFmpeg on CPU takes roughly 0.3x–0.8x real-time duration; GPU acceleration (`cuda`) further reduces latency when available.
- **Single-Node Background Queue**: FastAPI `BackgroundTasks` + SQLite is ideal for single-container deployments; horizontal multi-worker scaling requires an external broker.

---

## 4. Future Improvements
- **Semantic Visual Query Expansion**: Use a lightweight local LLM or embedding index to translate abstract sentences into concrete visual cinematography prompts.
- **Visual Deduplication & Clip Caching**: Cache downloaded Pexels/Pixabay clips by content hash across jobs and prevent the same clip URL from appearing twice in a single video.
- **Crossfade Transitions & Audio Ducking**: Add FFmpeg `xfade` transitions between scenes and background ambient music with sidechain compression under the voiceover.
