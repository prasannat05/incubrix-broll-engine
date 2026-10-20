from pathlib import Path
import pytest
import srt
from backend.schemas import SceneItem
from backend.services.audio_service import TranscriptSegment
from backend.services.broll_service import BRollService
from backend.services.scene_service import SceneService
from backend.services.subtitle_service import SubtitleService


def test_scene_splitting_by_paragraph_and_sentence():
    service = SceneService(pause_threshold=0.8)
    script = (
        "Cloud computing powers modern startups. Engineers deploy containers globally.\n\n"
        "Automated pipelines reduce manual overhead."
    )
    units = service.split_script_into_units(script)
    assert len(units) == 3
    assert units[0] == "Cloud computing powers modern startups."
    assert units[2] == "Automated pipelines reduce manual overhead."


def test_scene_detection_respects_pause_threshold():
    service = SceneService(pause_threshold=0.8)
    segments = [
        TranscriptSegment(start=0.0, end=1.2, text="First phrase here"),
        TranscriptSegment(start=1.3, end=2.4, text="continues without pause."),
        TranscriptSegment(start=3.6, end=5.0, text="New scene after pause gap."),
    ]
    scenes = service.detect_scenes_from_segments(segments)
    assert len(scenes) == 2
    assert scenes[0].start_time == 0.0
    assert scenes[0].end_time == 2.4
    assert scenes[1].start_time == 3.6
    assert len(scenes[0].keywords) >= 2


def test_subtitle_generation_produces_valid_srt(tmp_path: Path):
    scenes = [
        SceneItem(
            scene_id=1,
            start_time=0.0,
            end_time=2.5,
            text="First subtitle line.",
            keywords=["subtitle", "line"],
            selected_clip="clips/scene_001.mp4",
            clip_duration=2.5,
        ),
        SceneItem(
            scene_id=2,
            start_time=2.5,
            end_time=5.0,
            text="Second subtitle line.",
            keywords=["second", "line"],
            selected_clip="clips/scene_002.mp4",
            clip_duration=2.5,
        ),
    ]
    srt_path = tmp_path / "captions.srt"
    SubtitleService.generate_srt(scenes, srt_path)
    parsed = list(srt.parse(srt_path.read_text(encoding="utf-8")))
    assert len(parsed) == 2
    assert parsed[0].content == "First subtitle line."
    assert parsed[1].index == 2


@pytest.mark.asyncio
async def test_broll_fallback_manifest_generation(temp_workspace: Path):
    job_dir = temp_workspace / "jobs" / "test_job"
    broll = BRollService(
        pexels_api_key="",
        pixabay_api_key="",
        fallback_clip_path=temp_workspace / "assets" / "fallback_broll.mp4",
    )
    manifest_item, duration = await broll.acquire_clip_for_scene(
        scene_id=1,
        keywords=["mountain", "sunrise"],
        target_duration=2.0,
        job_dir=job_dir,
    )
    assert manifest_item.provider == "local_fallback"
    assert manifest_item.clip_name == "scene_001.mp4"
    assert duration > 0
    assert (job_dir / manifest_item.local_path).exists()
