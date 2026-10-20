import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from backend.config import settings
from backend.database import JobRepository, job_repo
from backend.exceptions import EngineError, JobTimeoutError, UnsupportedFileError
from backend.logger import get_job_logger, log_step
from backend.models import InputType, JobStatus
from backend.schemas import ManifestDocument, ManifestItem, SceneItem, TimelineDocument
from backend.services.audio_service import AudioService
from backend.services.broll_service import BRollService
from backend.services.scene_service import SceneService
from backend.services.subtitle_service import SubtitleService
from backend.services.video_service import VideoService


class VideoGenerationPipeline:
    """Coordinates the full asynchronous workflow from script/audio input to rendered MP4 & metadata."""

    def __init__(
        self,
        repository: JobRepository = job_repo,
        audio_service: Optional[AudioService] = None,
        scene_service: Optional[SceneService] = None,
        broll_service: Optional[BRollService] = None,
        subtitle_service: Optional[SubtitleService] = None,
        video_service: Optional[VideoService] = None,
    ):
        self.repo = repository
        self.audio_service = audio_service or AudioService()
        self.scene_service = scene_service or SceneService()
        self.broll_service = broll_service or BRollService()
        self.subtitle_service = subtitle_service or SubtitleService()
        self.video_service = video_service or VideoService()

    async def run_job(
        self,
        job_id: str,
        input_type: InputType,
        job_dir: Path,
        script_text: Optional[str] = None,
        audio_path: Optional[Path] = None,
    ) -> None:
        logger = get_job_logger(job_id, job_dir)
        log_step(logger, job_id, "INIT", f"Starting job {job_id} with input_type={input_type.value}")

        try:
            await asyncio.wait_for(
                self._execute_steps(
                    job_id=job_id,
                    input_type=input_type,
                    job_dir=job_dir,
                    logger=logger,
                    script_text=script_text,
                    audio_path=audio_path,
                ),
                timeout=settings.job_timeout_seconds,
            )
        except asyncio.TimeoutError:
            err = JobTimeoutError(job_id, settings.job_timeout_seconds)
            log_step(logger, job_id, "TIMEOUT", err.message, level=logging.ERROR)
            self.repo.update_job(
                job_id,
                status=JobStatus.FAILED,
                current_step="Failed: Timeout",
                error_code=err.error_code,
                error_message=err.message,
            )
        except EngineError as exc:
            log_step(logger, job_id, "ERROR", f"{exc.error_code}: {exc.message}", level=logging.ERROR)
            self.repo.update_job(
                job_id,
                status=JobStatus.FAILED,
                current_step=f"Failed: {exc.error_code}",
                error_code=exc.error_code,
                error_message=exc.message,
            )
        except Exception as exc:
            log_step(logger, job_id, "UNHANDLED_ERROR", str(exc), level=logging.ERROR)
            self.repo.update_job(
                job_id,
                status=JobStatus.FAILED,
                current_step="Failed: Internal Error",
                error_code="INTERNAL_ERROR",
                error_message=str(exc),
            )

    async def _execute_steps(
        self,
        job_id: str,
        input_type: InputType,
        job_dir: Path,
        logger: logging.Logger,
        script_text: Optional[str],
        audio_path: Optional[Path],
    ) -> None:
        self.repo.update_job(
            job_id,
            status=JobStatus.PROCESSING,
            progress=10,
            current_step="Preparing narration & transcript",
        )

        narration_path = job_dir / "narration.wav"

        if input_type == InputType.AUDIO:
            if not audio_path or not audio_path.exists():
                raise UnsupportedFileError("Audio file missing for audio job.")
            duration = await asyncio.to_thread(self.audio_service.validate_audio_duration, audio_path)
            log_step(logger, job_id, "AUDIO_VALIDATED", f"Validated audio duration: {duration:.2f}s")

            self.repo.update_job(job_id, progress=20, current_step="Transcribing audio with Whisper")
            segments = await asyncio.to_thread(self.audio_service.transcribe_audio, audio_path)
            narration_path = audio_path
            log_step(logger, job_id, "TRANSCRIPTION_COMPLETE", f"Extracted {len(segments)} Whisper segments")

            self.repo.update_job(job_id, progress=35, current_step="Splitting transcript into scenes")
            detected_scenes = self.scene_service.detect_scenes_from_segments(segments)
        else:
            if not script_text or not script_text.strip():
                raise UnsupportedFileError("Script text cannot be empty.")
            units = self.scene_service.split_script_into_units(script_text)
            if not units:
                raise UnsupportedFileError("No valid sentences found in script.")
            log_step(logger, job_id, "SCRIPT_SPLIT", f"Split script into {len(units)} scene units")

            self.repo.update_job(job_id, progress=25, current_step="Synthesizing voiceover narration")
            segments = await asyncio.to_thread(
                self.audio_service.synthesize_narration_for_scenes,
                units,
                narration_path,
                job_dir / "tts_work",
            )
            log_step(logger, job_id, "TTS_COMPLETE", f"Generated narration audio across {len(segments)} scenes")

            detected_scenes = [
                self.scene_service.detect_scenes_from_segments([seg], max_scene_duration=60.0)[0]
                for seg in segments
            ]
            for idx, sc in enumerate(detected_scenes, start=1):
                sc.scene_id = idx
                sc.keywords = self.scene_service.extract_keywords(sc.text, scene_id=idx)

        self.repo.update_job(job_id, progress=50, current_step="Searching & downloading B-roll clips")
        scene_items: list[SceneItem] = []
        manifest_assets: list[ManifestItem] = []

        for sc in detected_scenes:
            target_dur = max(1.0, sc.end_time - sc.start_time)
            log_step(
                logger,
                job_id,
                "BROLL_SEARCH",
                f"Scene {sc.scene_id} ({sc.start_time:.2f}s-{sc.end_time:.2f}s) keywords={sc.keywords}",
            )
            manifest_item, clip_dur = await self.broll_service.acquire_clip_for_scene(
                scene_id=sc.scene_id,
                keywords=sc.keywords,
                target_duration=target_dur,
                job_dir=job_dir,
            )
            manifest_assets.append(manifest_item)
            scene_items.append(
                SceneItem(
                    scene_id=sc.scene_id,
                    start_time=sc.start_time,
                    end_time=sc.end_time,
                    text=sc.text,
                    keywords=sc.keywords,
                    selected_clip=manifest_item.local_path,
                    clip_duration=clip_dur,
                )
            )
            log_step(
                logger,
                job_id,
                "BROLL_ACQUIRED",
                f"Scene {sc.scene_id} paired with {manifest_item.local_path} from {manifest_item.provider}",
            )

        # Write timeline.json and manifest.json
        self.repo.update_job(job_id, progress=70, current_step="Generating timeline, manifest & SRT captions")
        total_duration = round(scene_items[-1].end_time if scene_items else 0.0, 2)

        timeline_doc = TimelineDocument(
            job_id=job_id,
            input_type=input_type,
            total_duration=total_duration,
            scenes=scene_items,
        )
        timeline_path = job_dir / "timeline.json"
        timeline_path.write_text(timeline_doc.model_dump_json(indent=2), encoding="utf-8")

        manifest_doc = ManifestDocument(
            job_id=job_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            assets=manifest_assets,
        )
        manifest_path = job_dir / "manifest.json"
        manifest_path.write_text(manifest_doc.model_dump_json(indent=2), encoding="utf-8")

        captions_path = job_dir / "captions.srt"
        self.subtitle_service.generate_srt(scene_items, captions_path)
        log_step(logger, job_id, "METADATA_SAVED", "Saved timeline.json, manifest.json, and captions.srt")

        # Render final MP4 via FFmpeg
        self.repo.update_job(job_id, progress=85, current_step="Rendering final MP4 video with FFmpeg")
        video_path = job_dir / "video.mp4"
        await asyncio.to_thread(
            self.video_service.render_video,
            scene_items,
            narration_path,
            captions_path,
            job_dir,
            video_path,
        )
        log_step(logger, job_id, "RENDER_COMPLETE", f"Rendered final video at {video_path}")

        self.repo.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            current_step="Completed",
        )
        log_step(logger, job_id, "COMPLETED", f"Job {job_id} completed successfully")
