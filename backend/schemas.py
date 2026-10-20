from typing import Optional
from pydantic import BaseModel, Field
from backend.models import InputType, JobStatus


class SceneItem(BaseModel):
    scene_id: int = Field(..., description="1-based sequential identifier for the scene")
    start_time: float = Field(..., ge=0.0, description="Start timestamp in seconds")
    end_time: float = Field(..., gt=0.0, description="End timestamp in seconds")
    text: str = Field(..., description="Transcript text corresponding to this scene")
    keywords: list[str] = Field(..., description="Extracted search keywords for B-roll retrieval")
    selected_clip: str = Field(..., description="Filename or path of the selected B-roll video clip")
    clip_duration: float = Field(..., gt=0.0, description="Duration of the selected B-roll clip in seconds")


class TimelineDocument(BaseModel):
    job_id: str
    input_type: InputType
    total_duration: float
    scenes: list[SceneItem]


class ManifestItem(BaseModel):
    clip_name: str = Field(..., description="Filename of the downloaded B-roll clip")
    provider: str = Field(..., description="Stock footage provider (pexels, pixabay, or local_fallback)")
    original_url: str = Field(..., description="Source URL of the media asset")
    license: str = Field(..., description="Commercial license identifier")
    author: str = Field(..., description="Creator or author of the footage")
    download_time: str = Field(..., description="ISO-8601 UTC timestamp of download")
    local_path: str = Field(..., description="Relative local path within the job folder")


class ManifestDocument(BaseModel):
    job_id: str
    generated_at: str
    assets: list[ManifestItem]


class GenerateResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = Field(..., ge=0, le=100)
    current_step: str
    input_type: InputType
    created_at: str
    updated_at: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class ResultLinksResponse(BaseModel):
    job_id: str
    status: JobStatus
    files: dict[str, str]
    timeline: TimelineDocument
    manifest: ManifestDocument
