import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from backend.config import settings
from backend.exceptions import AudioTooLongError, RenderingFailedError, UnsupportedFileError

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav"}
ALLOWED_SCRIPT_EXTENSIONS = {".txt"}


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


class AudioService:
    """Handles audio validation, Whisper speech-to-text transcription, and script TTS synthesis."""

    def __init__(self, model_size: str = settings.whisper_model_size):
        self.model_size = model_size
        self._whisper_model: Any = None

    def _load_whisper(self) -> Any:
        if self._whisper_model is None:
            from faster_whisper import WhisperModel
            self._whisper_model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._whisper_model

    @staticmethod
    def validate_audio_extension(filename: str) -> None:
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            raise UnsupportedFileError(
                f"Unsupported audio format '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}"
            )

    @staticmethod
    def validate_script_extension(filename: str) -> None:
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_SCRIPT_EXTENSIONS:
            raise UnsupportedFileError(
                f"Unsupported script file format '{ext}'. Allowed format: .txt"
            )

    @staticmethod
    def probe_duration(media_path: Path) -> float:
        """Probe exact media duration in seconds using ffprobe."""
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(media_path),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            data = json.loads(proc.stdout)
            return float(data["format"]["duration"])
        except Exception as exc:
            raise RenderingFailedError(f"Failed to probe media duration for {media_path.name}: {exc}") from exc

    def validate_audio_duration(self, audio_path: Path) -> float:
        duration = self.probe_duration(audio_path)
        if duration > settings.max_audio_duration_seconds:
            raise AudioTooLongError(duration, settings.max_audio_duration_seconds)
        if duration <= 0.1:
            raise UnsupportedFileError("Uploaded audio file is empty or shorter than 0.1 seconds.")
        return duration

    def transcribe_audio(self, audio_path: Path) -> list[TranscriptSegment]:
        """Transcribe voiceover recording using faster-whisper with segment timing."""
        model = self._load_whisper()
        raw_segments, info = model.transcribe(str(audio_path), beam_size=5, word_timestamps=False)
        segments: list[TranscriptSegment] = []

        for seg in raw_segments:
            text = str(seg.text).strip()
            if not text:
                continue
            start = max(0.0, float(seg.start))
            end = max(start + 0.5, float(seg.end))
            segments.append(TranscriptSegment(start=round(start, 2), end=round(end, 2), text=text))

        if not segments:
            duration = float(info.duration) if info.duration else self.probe_duration(audio_path)
            segments.append(TranscriptSegment(start=0.0, end=round(duration, 2), text="Instrumental or ambient voiceover segment."))

        return segments

    def synthesize_narration_for_scenes(
        self, scene_texts: list[str], output_audio_path: Path, work_dir: Path
    ) -> list[TranscriptSegment]:
        """
        Generate synchronized voiceover narration for plain-text scripts.
        Uses gTTS when internet is available, with an automatic deterministic FFmpeg
        synthesized voice/tone fallback so offline or air-gapped environments never fail.
        """
        work_dir.mkdir(parents=True, exist_ok=True)
        part_files: list[Path] = []
        segments: list[TranscriptSegment] = []
        current_time = 0.0

        for idx, text in enumerate(scene_texts, start=1):
            part_wav = work_dir / f"tts_scene_{idx:03d}.wav"
            synthesized = False

            try:
                from gtts import gTTS
                mp3_temp = work_dir / f"tts_scene_{idx:03d}.mp3"
                tts = gTTS(text=text, lang="en", slow=False)
                tts.save(str(mp3_temp))
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(mp3_temp),
                        "-ar",
                        "44100",
                        "-ac",
                        "2",
                        str(part_wav),
                    ],
                    capture_output=True,
                    check=True,
                    timeout=30,
                )
                synthesized = True
            except Exception:
                synthesized = False

            if not synthesized:
                word_count = max(1, len(text.split()))
                estimated_seconds = max(2.5, round(word_count / 2.6, 2))
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        f"sine=frequency=220:sample_rate=44100:duration={estimated_seconds}",
                        "-af",
                        "volume=0.03",
                        "-ac",
                        "2",
                        str(part_wav),
                    ],
                    capture_output=True,
                    check=True,
                    timeout=30,
                )

            seg_duration = self.probe_duration(part_wav)
            start_t = round(current_time, 2)
            end_t = round(current_time + seg_duration, 2)
            segments.append(TranscriptSegment(start=start_t, end=end_t, text=text))
            current_time = end_t
            part_files.append(part_wav)

        concat_list = work_dir / "tts_concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in part_files),
            encoding="utf-8",
        )
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-c:a",
                "pcm_s16le",
                str(output_audio_path),
            ],
            capture_output=True,
            check=True,
            timeout=60,
        )
        return segments
