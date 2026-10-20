import io
import json
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.datastructures import UploadFile
from backend.config import settings
from backend.database import job_repo
from backend.exceptions import EngineError, UnsupportedFileError
from backend.models import InputType, JobStatus
from backend.schemas import (
    GenerateResponse,
    JobStatusResponse,
    ManifestDocument,
    ResultLinksResponse,
    TimelineDocument,
)
from backend.services.audio_service import AudioService
from backend.services.broll_service import BRollService
from backend.services.pipeline import VideoGenerationPipeline

pipeline = VideoGenerationPipeline()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    settings.assets_dir.mkdir(parents=True, exist_ok=True)
    try:
        BRollService().ensure_local_fallback_clip()
    except Exception:
        pass
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Converts plain text scripts or voice recordings (.mp3/.wav) into synchronized B-roll videos with captions, timeline metadata, and asset manifests.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(EngineError)
async def engine_error_handler(_: Request, exc: EngineError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.error_code, "detail": exc.message},
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": settings.app_name}


@app.post("/generate", response_model=GenerateResponse, status_code=202)
async def generate_video(request: Request, background_tasks: BackgroundTasks) -> GenerateResponse:
    """
    Accepts `multipart/form-data` with either:
    - `script` (plain text string OR uploaded `.txt` file)
    - `audio` (uploaded `.mp3` or `.wav` file)
    Starts asynchronous generation and returns `job_id`.
    """
    form = await request.form()
    script_field = form.get("script")
    audio_field = form.get("audio")

    if not script_field and not audio_field:
        raise UnsupportedFileError("Provide either 'script' (text or .txt file) or 'audio' (.mp3/.wav file).")

    job_id = str(uuid.uuid4())
    job_dir = settings.jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Case 1: Audio upload provided
    if isinstance(audio_field, UploadFile) and audio_field.filename:
        AudioService.validate_audio_extension(audio_field.filename)
        ext = Path(audio_field.filename).suffix.lower()
        saved_audio_path = job_dir / f"voice{ext}"
        content = await audio_field.read()
        if len(content) > settings.max_upload_size_mb * 1024 * 1024:
            raise UnsupportedFileError(f"Uploaded file exceeds {settings.max_upload_size_mb}MB limit.")
        saved_audio_path.write_bytes(content)

        # Synchronously validate audio duration before queueing so invalid files fail fast with 400
        pipeline.audio_service.validate_audio_duration(saved_audio_path)

        job_repo.create_job(job_id=job_id, input_type=InputType.AUDIO)
        background_tasks.add_task(
            pipeline.run_job,
            job_id=job_id,
            input_type=InputType.AUDIO,
            job_dir=job_dir,
            audio_path=saved_audio_path,
        )
        return GenerateResponse(job_id=job_id, status=JobStatus.QUEUED, message="Audio job queued for processing.")

    # Case 2: Script uploaded as a file (.txt) or plain text form field
    script_text: Optional[str] = None
    if isinstance(script_field, UploadFile) and script_field.filename:
        AudioService.validate_script_extension(script_field.filename)
        raw_bytes = await script_field.read()
        script_text = raw_bytes.decode("utf-8", errors="replace").strip()
    elif isinstance(script_field, str):
        script_text = script_field.strip()

    if not script_text:
        raise UnsupportedFileError("Uploaded script is empty or unsupported.")

    (job_dir / "script.txt").write_text(script_text, encoding="utf-8")
    job_repo.create_job(job_id=job_id, input_type=InputType.SCRIPT)
    background_tasks.add_task(
        pipeline.run_job,
        job_id=job_id,
        input_type=InputType.SCRIPT,
        job_dir=job_dir,
        script_text=script_text,
    )
    return GenerateResponse(job_id=job_id, status=JobStatus.QUEUED, message="Script job queued for processing.")


@app.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    job = job_repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return JobStatusResponse(**job)


ARTIFACT_MAP = {
    "video": ("video.mp4", "video/mp4"),
    "captions": ("captions.srt", "application/x-subrip"),
    "timeline": ("timeline.json", "application/json"),
    "manifest": ("manifest.json", "application/json"),
    "logs": ("logs.txt", "text/plain"),
}


@app.get("/result/{job_id}")
async def get_job_result(
    job_id: str,
    file: Optional[str] = Query(
        default=None,
        description="Optional artifact to download directly: video, captions, timeline, manifest, logs, or zip",
    ),
):
    """
    Returns job results:
    - Without `?file=...`: returns JSON containing download URLs and parsed `timeline.json` & `manifest.json`.
    - With `?file=video|captions|timeline|manifest|logs`: downloads the specific file.
    - With `?file=zip`: streams a ZIP archive containing `video.mp4`, `captions.srt`, `timeline.json`, `manifest.json`, and `logs.txt`.
    """
    job = job_repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    if job["status"] != JobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=409,
            detail=f"Job '{job_id}' is currently '{job['status']}' and not yet completed.",
        )

    job_dir = settings.jobs_dir / job_id

    if file == "zip":
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename, _ in ARTIFACT_MAP.values():
                fpath = job_dir / filename
                if fpath.exists():
                    zf.write(fpath, arcname=filename)
        zip_buffer.seek(0)
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="job_{job_id}_bundle.zip"'},
        )

    if file is not None:
        if file not in ARTIFACT_MAP:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file parameter '{file}'. Must be one of: {', '.join(ARTIFACT_MAP.keys())}, zip",
            )
        filename, media_type = ARTIFACT_MAP[file]
        target_path = job_dir / filename
        if not target_path.exists():
            raise HTTPException(status_code=404, detail=f"Artifact '{filename}' not found for job '{job_id}'.")
        return FileResponse(path=target_path, media_type=media_type, filename=filename)

    timeline_data = json.loads((job_dir / "timeline.json").read_text(encoding="utf-8"))
    manifest_data = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))

    return ResultLinksResponse(
        job_id=job_id,
        status=JobStatus.COMPLETED,
        files={
            "video": f"/result/{job_id}?file=video",
            "captions": f"/result/{job_id}?file=captions",
            "timeline": f"/result/{job_id}?file=timeline",
            "manifest": f"/result/{job_id}?file=manifest",
            "logs": f"/result/{job_id}?file=logs",
            "zip": f"/result/{job_id}?file=zip",
        },
        timeline=TimelineDocument(**timeline_data),
        manifest=ManifestDocument(**manifest_data),
    )
