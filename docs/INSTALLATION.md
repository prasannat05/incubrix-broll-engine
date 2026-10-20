# Detailed Installation Guide

## 1. Local Native Setup (Ubuntu / macOS / WSL2)
1. Install system dependencies:
   - Ubuntu/Debian: `sudo apt-get update && sudo apt-get install -y ffmpeg python3.12 python3.12-venv nodejs npm`
   - macOS: `brew install ffmpeg python@3.12 node`
2. Configure environment variables:
   - `cp .env.example .env`
   - Add `PEXELS_API_KEY` and `PIXABAY_API_KEY`.
3. Install Python packages & initialize fallback clip:
   - `python3.12 -m venv .venv && source .venv/bin/activate`
   - `pip install -r requirements.txt`
   - `python -m assets.ensure_fallback`
4. Run tests:
   - `pytest -v`
5. Launch backend & frontend:
   - Terminal 1: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`
   - Terminal 2: `cd frontend && npm install && npm run dev`

## 2. Docker Compose Setup
1. `cp .env.example .env`
2. `docker compose up --build -d`
3. Access the UI at `http://localhost:3000` and API at `http://localhost:8000`.
