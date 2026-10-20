import json
from pathlib import Path
import pytest
from backend.main import pipeline
from backend.models import InputType, JobStatus


@pytest.mark.asyncio
async def test_end_to_end_script_pipeline(temp_workspace: Path):
    job_id = "pipeline-script-001"
    job_dir = temp_workspace / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    pipeline.repo.create_job(job_id, InputType.SCRIPT)

    await pipeline.run_job(
        job_id=job_id,
        input_type=InputType.SCRIPT,
        job_dir=job_dir,
        script_text="Solar energy is growing rapidly.\n\nWind turbines generate clean electricity.",
    )

    job = pipeline.repo.get_job(job_id)
    assert job is not None
    assert job["status"] == JobStatus.COMPLETED.value

    assert (job_dir / "video.mp4").exists()
    assert (job_dir / "captions.srt").exists()
    assert (job_dir / "timeline.json").exists()
    assert (job_dir / "manifest.json").exists()
    assert (job_dir / "logs.txt").exists()

    timeline = json.loads((job_dir / "timeline.json").read_text(encoding="utf-8"))
    assert len(timeline["scenes"]) == 2
    first_scene = timeline["scenes"][0]
    for required_key in (
        "scene_id",
        "start_time",
        "end_time",
        "text",
        "keywords",
        "selected_clip",
        "clip_duration",
    ):
        assert required_key in first_scene

    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["assets"]) == 2
    first_asset = manifest["assets"][0]
    for required_key in (
        "clip_name",
        "provider",
        "original_url",
        "license",
        "author",
        "download_time",
        "local_path",
    ):
        assert required_key in first_asset
