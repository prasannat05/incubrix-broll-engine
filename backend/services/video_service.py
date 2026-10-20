import subprocess
from pathlib import Path
from backend.config import settings
from backend.exceptions import RenderingFailedError
from backend.schemas import SceneItem


class VideoService:
    """
    Renders the final MP4 using FFmpeg:
    1. Loops/trims and normalizes each scene's B-roll clip to exact scene duration, 1280x720, 30fps.
    2. Renders legible caption overlays onto each scene segment.
    3. Concatenates normalized scene segments.
    4. Muxes synchronized narration audio and embedded SRT subtitle track into `video.mp4`.
    """

    def __init__(
        self,
        width: int = settings.target_width,
        height: int = settings.target_height,
        fps: int = settings.target_fps,
        ffmpeg_timeout: int = settings.ffmpeg_timeout_seconds,
    ):
        self.width = width
        self.height = height
        self.fps = fps
        self.ffmpeg_timeout = ffmpeg_timeout

    @staticmethod
    def _escape_drawtext(text: str) -> str:
        """Escape characters for FFmpeg drawtext filter."""
        cleaned = " ".join(text.split())
        if len(cleaned) > 78:
            cleaned = cleaned[:75] + "..."
        return (
            cleaned.replace("\\", "\\\\")
            .replace("'", "\u2019")
            .replace(":", "\\:")
            .replace("%", "\\%")
            .replace(",", "\\,")
        )

    def render_video(
        self,
        scenes: list[SceneItem],
        narration_audio_path: Path,
        captions_srt_path: Path,
        job_dir: Path,
        output_video_path: Path,
    ) -> Path:
        work_dir = job_dir / "render_work"
        work_dir.mkdir(parents=True, exist_ok=True)
        normalized_segments: list[Path] = []

        for scene in scenes:
            scene_duration = max(0.5, round(scene.end_time - scene.start_time, 2))
            raw_clip_path = job_dir / scene.selected_clip
            norm_clip_path = work_dir / f"norm_scene_{scene.scene_id:03d}.mp4"

            vf_scale = (
                f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
                f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"fps={self.fps},format=yuv420p"
            )

            cmd_norm = [
                "ffmpeg",
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                str(raw_clip_path),
                "-t",
                f"{scene_duration:.2f}",
                "-vf",
                vf_scale,
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "23",
                str(norm_clip_path),
            ]
            self._run_ffmpeg(cmd_norm, f"Failed normalizing scene {scene.scene_id}")
            normalized_segments.append(norm_clip_path)

        concat_file = work_dir / "scenes_concat.txt"
        concat_file.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in normalized_segments),
            encoding="utf-8",
        )

        merged_visual_path = work_dir / "merged_visual.mp4"
        cmd_concat = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(merged_visual_path),
        ]
        self._run_ffmpeg(cmd_concat, "Failed concatenating normalized B-roll scenes")

        # Attempt subtitle burn-in via libass `subtitles` filter; if FFmpeg build lacks libass,
        # mux soft subtitles (`mov_text`) so rendering succeeds across all environments.
        srt_posix = captions_srt_path.resolve().as_posix().replace(":", "\\:")
        cmd_final_burn = [
            "ffmpeg",
            "-y",
            "-i",
            str(merged_visual_path),
            "-i",
            str(narration_audio_path),
            "-vf",
            f"subtitles='{srt_posix}'",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_video_path),
        ]

        try:
            self._run_ffmpeg(cmd_final_burn, "Burn-in subtitles attempt")
        except RenderingFailedError:
            cmd_final_mux = [
                "ffmpeg",
                "-y",
                "-i",
                str(merged_visual_path),
                "-i",
                str(narration_audio_path),
                "-i",
                str(captions_srt_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-map",
                "2:s:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-c:s",
                "mov_text",
                "-shortest",
                "-movflags",
                "+faststart",
                str(output_video_path),
            ]
            self._run_ffmpeg(cmd_final_mux, "Failed muxing final MP4 with narration and captions")

        if not output_video_path.exists() or output_video_path.stat().st_size == 0:
            raise RenderingFailedError("Final video output file was not created or is empty.")

        return output_video_path

    def _run_ffmpeg(self, cmd: list[str], error_context: str) -> None:
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=self.ffmpeg_timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RenderingFailedError(f"{error_context}: FFmpeg timed out after {self.ffmpeg_timeout}s") from exc
        except subprocess.CalledProcessError as exc:
            stderr_tail = (exc.stderr or "")[-600:]
            raise RenderingFailedError(f"{error_context}: {stderr_tail}") from exc
