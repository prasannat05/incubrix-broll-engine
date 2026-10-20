import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import httpx
from backend.config import settings
from backend.exceptions import NoBRollFoundError
from backend.schemas import ManifestItem
from backend.services.audio_service import AudioService


class BRollService:
    """
    Searches Pexels API (primary) and Pixabay API (secondary) for commercial-safe B-roll footage.
    Implements automatic query retry, fallback keyword cascade, and local generic fallback clip.
    """

    def __init__(
        self,
        pexels_api_key: str = settings.pexels_api_key,
        pixabay_api_key: str = settings.pixabay_api_key,
        fallback_clip_path: Path = settings.fallback_clip_path,
        timeout_seconds: float = settings.api_timeout_seconds,
    ):
        self.pexels_api_key = pexels_api_key
        self.pixabay_api_key = pixabay_api_key
        self.fallback_clip_path = fallback_clip_path
        self.timeout_seconds = timeout_seconds

    def ensure_local_fallback_clip(self) -> Path:
        """Create a commercial-safe 1280x720 30fps MP4 fallback clip via FFmpeg if not already present."""
        self.fallback_clip_path.parent.mkdir(parents=True, exist_ok=True)
        if self.fallback_clip_path.exists() and self.fallback_clip_path.stat().st_size > 1024:
            return self.fallback_clip_path

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x1e293b:s={settings.target_width}x{settings.target_height}:r={settings.target_fps}:d=6",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(self.fallback_clip_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=30)
        return self.fallback_clip_path

    async def acquire_clip_for_scene(
        self,
        scene_id: int,
        keywords: list[str],
        target_duration: float,
        job_dir: Path,
    ) -> tuple[ManifestItem, float]:
        """
        Search for the highest-relevance commercial B-roll clip matching scene keywords.
        Cascade order:
        1. Primary compound query on Pexels ("kw1 kw2")
        2. Individual keyword retry on Pexels ("kw1", "kw2")
        3. Primary & fallback keyword retry on Pixabay
        4. Fallback generic keyword ("nature", "abstract") on Pexels/Pixabay
        5. Local synthesized fallback clip
        """
        clips_dir = job_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        clip_filename = f"scene_{scene_id:03d}.mp4"
        dest_path = clips_dir / clip_filename

        queries: list[str] = []
        if len(keywords) >= 2:
            queries.append(f"{keywords[0]} {keywords[1]}")
        queries.extend(keywords)
        queries.append("cinematic nature")

        # 1. Try Pexels API if configured
        if self.pexels_api_key:
            for query in queries:
                candidate = await self._search_pexels(query, target_duration)
                if candidate and await self._download_file(candidate["download_url"], dest_path):
                    duration = AudioService.probe_duration(dest_path)
                    manifest_item = ManifestItem(
                        clip_name=clip_filename,
                        provider="pexels",
                        original_url=candidate["page_url"],
                        license="Pexels License (Free for commercial use, no attribution required)",
                        author=candidate["author"],
                        download_time=datetime.now(timezone.utc).isoformat(),
                        local_path=f"clips/{clip_filename}",
                    )
                    return manifest_item, round(duration, 2)

        # 2. Try Pixabay API if configured
        if self.pixabay_api_key:
            for query in queries:
                candidate = await self._search_pixabay(query, target_duration)
                if candidate and await self._download_file(candidate["download_url"], dest_path):
                    duration = AudioService.probe_duration(dest_path)
                    manifest_item = ManifestItem(
                        clip_name=clip_filename,
                        provider="pixabay",
                        original_url=candidate["page_url"],
                        license="Pixabay Content License (Free for commercial and non-commercial use)",
                        author=candidate["author"],
                        download_time=datetime.now(timezone.utc).isoformat(),
                        local_path=f"clips/{clip_filename}",
                    )
                    return manifest_item, round(duration, 2)

        # 3. Fallback to guaranteed local generic clip
        fallback_src = self.ensure_local_fallback_clip()
        if not fallback_src.exists():
            raise NoBRollFoundError(f"Could not find B-roll for scene {scene_id} and fallback clip is unavailable.")

        shutil.copyfile(fallback_src, dest_path)
        duration = AudioService.probe_duration(dest_path)
        manifest_item = ManifestItem(
            clip_name=clip_filename,
            provider="local_fallback",
            original_url="file://assets/fallback_broll.mp4",
            license="CC0 1.0 Universal (Public Domain / Self-Generated Fallback Asset)",
            author="IncuBrix Engine Synthesizer",
            download_time=datetime.now(timezone.utc).isoformat(),
            local_path=f"clips/{clip_filename}",
        )
        return manifest_item, round(duration, 2)

    async def _search_pexels(self, query: str, target_duration: float) -> Optional[dict[str, Any]]:
        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": self.pexels_api_key}
        params = {"query": query, "per_page": 8, "orientation": "landscape"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code != 200:
                    return None
                data = resp.json()
        except Exception:
            return None

        videos = data.get("videos", [])
        if not videos:
            return None

        best_video = min(
            videos,
            key=lambda v: abs(float(v.get("duration", 5.0)) - target_duration),
        )
        video_files = best_video.get("video_files", [])
        mp4_files = [vf for vf in video_files if vf.get("file_type") == "video/mp4" and vf.get("link")]
        if not mp4_files:
            return None

        chosen_file = min(
            mp4_files,
            key=lambda vf: abs(int(vf.get("width") or 1280) - settings.target_width),
        )
        user_info = best_video.get("user", {})
        return {
            "download_url": chosen_file["link"],
            "page_url": best_video.get("url", "https://www.pexels.com"),
            "author": user_info.get("name", "Pexels Contributor"),
        }

    async def _search_pixabay(self, query: str, target_duration: float) -> Optional[dict[str, Any]]:
        url = "https://pixabay.com/api/videos/"
        params = {
            "key": self.pixabay_api_key,
            "q": query,
            "per_page": 8,
            "safesearch": "true",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    return None
                data = resp.json()
        except Exception:
            return None

        hits = data.get("hits", [])
        if not hits:
            return None

        best_hit = min(
            hits,
            key=lambda h: abs(float(h.get("duration", 5.0)) - target_duration),
        )
        videos_dict = best_hit.get("videos", {})
        for tier in ("medium", "large", "small", "tiny"):
            tier_obj = videos_dict.get(tier, {})
            if tier_obj.get("url"):
                return {
                    "download_url": tier_obj["url"],
                    "page_url": best_hit.get("pageURL", "https://pixabay.com"),
                    "author": best_hit.get("user", "Pixabay Contributor"),
                }
        return None

    async def _download_file(self, url: str, dest_path: Path) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds * 2, follow_redirects=True) as client:
                async with client.stream("GET", url) as resp:
                    if resp.status_code != 200:
                        return False
                    with dest_path.open("wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            f.write(chunk)
            return dest_path.exists() and dest_path.stat().st_size > 1024
        except Exception:
            return False
