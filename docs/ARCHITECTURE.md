# System Architecture Details

## Sequence of Operations
1. Client sends `POST /generate` (`multipart/form-data`) with either `script` or `audio`.
2. FastAPI validates file extensions and audio length (`<= 600s`), creates a record in SQLite (`status = queued`), and schedules `VideoGenerationPipeline.run_job`.
3. `AudioService` produces timed `TranscriptSegment` items (via Whisper for audio, or per-scene TTS + `ffprobe` for plain scripts).
4. `SceneService` groups segments by punctuation and pause duration (`>= 0.8s`) and extracts ranked keywords.
5. `BRollService` queries Pexels, falls back to Pixabay, and falls back to `assets/fallback_broll.mp4`, recording provenance in `manifest.json`.
6. `SubtitleService` generates `captions.srt` and `VideoService` runs FFmpeg to produce `video.mp4`.
7. Client polls `GET /status/{job_id}` until `completed` and fetches artifacts from `GET /result/{job_id}`.
