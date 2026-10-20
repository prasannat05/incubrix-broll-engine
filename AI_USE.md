# AI Models & Tools Disclosure (`AI_USE.md`)

## 1. Runtime AI Models Used Inside the Application

| Model / Tool | Role in Pipeline | License | Execution Mode |
|---|---|---|---|
| **faster-whisper (`faster-whisper`)** | Speech-to-text transcription and segment timestamp alignment for uploaded `.mp3`/`.wav` voice recordings | MIT License | Local open-source inference (CTranslate2) |
| **Google Text-to-Speech (`gTTS`) + FFmpeg Synth Fallback** | Generates synchronized voiceover narration when the user uploads a plain-text `script.txt` | MIT License | API + Local FFmpeg deterministic fallback |

## 2. Development & Engineering AI Assistance
- **Architecture, Code Implementation & Test Suite Generation**: Gemini was used as an engineering collaborator to structure the FastAPI backend, React + Vite dark-theme frontend, FFmpeg normalization filtergraphs, OpenAPI 3.1 specification, and Pytest test suite.
- **Verification**: All generated schemas (`timeline.json`, `manifest.json`), error codes, and FFmpeg commands were verified against the IncuBrix PS3 assessment brief.
