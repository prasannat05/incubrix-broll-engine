import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.config import settings
from backend.database import JobRepository
from backend.main import app, pipeline
from backend.services.audio_service import TranscriptSegment


@pytest.fixture()
def temp_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    jobs_dir = tmp_path / "jobs"
    assets_dir = tmp_path / "assets"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    fallback_clip = assets_dir / "fallback_broll.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x1e293b:s=640x360:r=24:d=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(fallback_clip),
        ],
        capture_output=True,
        check=True,
    )

    monkeypatch.setattr(settings, "jobs_dir", jobs_dir)
    monkeypatch.setattr(settings, "assets_dir", assets_dir)
    monkeypatch.setattr(settings, "fallback_clip_path", fallback_clip)
    monkeypatch.setattr(settings, "target_width", 640)
    monkeypatch.setattr(settings, "target_height", 360)
    monkeypatch.setattr(settings, "target_fps", 24)

    test_repo = JobRepository(db_path=jobs_dir / "test_broll.db")
    monkeypatch.setattr("backend.main.job_repo", test_repo)
    monkeypatch.setattr(pipeline, "repo", test_repo)
    monkeypatch.setattr(pipeline.broll_service, "fallback_clip_path", fallback_clip)
    monkeypatch.setattr(pipeline.broll_service, "pexels_api_key", "")
    monkeypatch.setattr(pipeline.broll_service, "pixabay_api_key", "")

    def fake_transcribe(_: Path) -> list[TranscriptSegment]:
        return [
            TranscriptSegment(start=0.0, end=1.5, text="Welcome to the automated video engine."),
            TranscriptSegment(start=2.5, end=4.0, text="Everything is synchronized with B-roll clips."),
        ]

    monkeypatch.setattr(pipeline.audio_service, "transcribe_audio", fake_transcribe)
    return tmp_path


@pytest.fixture()
def sample_wav(tmp_path: Path) -> Path:
    wav_path = tmp_path / "sample_voice.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100:duration=4",
            str(wav_path),
        ],
        capture_output=True,
        check=True,
    )
    return wav_path


@pytest.fixture()
def client(temp_workspace: Path) -> TestClient:
    return TestClient(app)
