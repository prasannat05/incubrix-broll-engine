"""Generates the default commercial-safe fallback clip in `assets/fallback_broll.mp4`."""
from backend.services.broll_service import BRollService

if __name__ == "__main__":
    path = BRollService().ensure_local_fallback_clip()
    print(f"Fallback B-roll clip ready at: {path}")
