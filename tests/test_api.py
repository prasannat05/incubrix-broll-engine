from pathlib import Path
from fastapi.testclient import TestClient
from backend.config import settings


def test_post_generate_script_and_retrieve_results(client: TestClient):
    resp = client.post(
        "/generate",
        files={"script": ("script.txt", b"First test sentence.\n\nSecond test sentence.", "text/plain")},
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    status_resp = client.get(f"/status/{job_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "completed"

    result_resp = client.get(f"/result/{job_id}")
    assert result_resp.status_code == 200
    body = result_resp.json()
    assert "timeline" in body
    assert "manifest" in body

    video_dl = client.get(f"/result/{job_id}?file=video")
    assert video_dl.status_code == 200
    assert video_dl.headers["content-type"] == "video/mp4"


def test_post_generate_audio_upload(client: TestClient, sample_wav: Path):
    with sample_wav.open("rb") as f:
        resp = client.post("/generate", files={"audio": ("voice.wav", f, "audio/wav")})
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    status_resp = client.get(f"/status/{job_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "completed"


def test_reject_unsupported_file_extension(client: TestClient):
    resp = client.post("/generate", files={"audio": ("virus.exe", b"binarydata", "application/octet-stream")})
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "UNSUPPORTED_FILE"


def test_reject_audio_too_long(client: TestClient, sample_wav: Path, monkeypatch):
    monkeypatch.setattr(settings, "max_audio_duration_seconds", 1.0)
    with sample_wav.open("rb") as f:
        resp = client.post("/generate", files={"audio": ("voice.wav", f, "audio/wav")})
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "AUDIO_TOO_LONG"
