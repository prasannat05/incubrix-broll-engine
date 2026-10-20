from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "IncuBrix B-Roll Video Engine"
    app_env: str = "production"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    pexels_api_key: str = ""
    pixabay_api_key: str = ""

    database_path: Path = Path("./jobs/broll_engine.db")
    jobs_dir: Path = Path("./jobs")
    assets_dir: Path = Path("./assets")
    fallback_clip_path: Path = Path("./assets/fallback_broll.mp4")

    whisper_model_size: str = "base"
    max_audio_duration_seconds: float = 600.0
    max_upload_size_mb: int = 50
    api_timeout_seconds: float = 15.0
    ffmpeg_timeout_seconds: int = 300
    job_timeout_seconds: int = 600
    pause_threshold_seconds: float = 0.8

    target_width: int = 1280
    target_height: int = 720
    target_fps: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
settings.jobs_dir.mkdir(parents=True, exist_ok=True)
settings.assets_dir.mkdir(parents=True, exist_ok=True)
