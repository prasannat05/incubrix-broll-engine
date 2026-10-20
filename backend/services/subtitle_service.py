from datetime import timedelta
from pathlib import Path
import srt
from backend.schemas import SceneItem


class SubtitleService:
    """Generates standard SubRip (.srt) caption files synchronized to scene timing using Python `srt`."""

    @staticmethod
    def generate_srt(scenes: list[SceneItem], output_srt_path: Path) -> Path:
        subtitles: list[srt.Subtitle] = []
        for scene in scenes:
            start_td = timedelta(seconds=max(0.0, scene.start_time))
            end_td = timedelta(seconds=max(scene.start_time + 0.5, scene.end_time))
            content = srt.make_legal_content(scene.text.strip())
            subtitles.append(
                srt.Subtitle(
                    index=scene.scene_id,
                    start=start_td,
                    end=end_td,
                    content=content,
                )
            )

        composed = srt.compose(subtitles)
        output_srt_path.parent.mkdir(parents=True, exist_ok=True)
        output_srt_path.write_text(composed, encoding="utf-8")
        return output_srt_path
