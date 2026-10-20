import React, { useState, useEffect, useRef } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

const SAMPLE_SCRIPT = `Artificial intelligence is transforming modern video production across the globe.
Teams can now convert written scripts into synchronized visual stories in minutes.

High quality stock footage and automated captioning make content accessible everywhere.`;

export default function App() {
  const [mode, setMode] = useState("script"); // "script" | "audio"
  const [scriptText, setScriptText] = useState(SAMPLE_SCRIPT);
  const [scriptFile, setScriptFile] = useState(null);
  const [audioFile, setAudioFile] = useState(null);

  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState("");
  const [errorMsg, setErrorMsg] = useState(null);
  const [resultData, setResultData] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const pollTimerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, []);

  const startPolling = (id) => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);

    pollTimerRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/status/${id}`);
        if (!res.ok) throw new Error("Failed to fetch job status");
        const data = await res.json();

        setJobStatus(data.status);
        setProgress(data.progress);
        setCurrentStep(data.current_step);

        if (data.status === "completed") {
          clearInterval(pollTimerRef.current);
          const resultRes = await fetch(`${API_BASE}/result/${id}`);
          if (resultRes.ok) {
            const fullResult = await resultRes.json();
            setResultData(fullResult);
          }
        } else if (data.status === "failed") {
          clearInterval(pollTimerRef.current);
          setErrorMsg(data.error_message || "Video generation job failed.");
        }
      } catch (err) {
        setErrorMsg(err.message);
        clearInterval(pollTimerRef.current);
      }
    }, 1500);
  };

  const handleGenerate = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    setResultData(null);
    setJobId(null);
    setJobStatus(null);
    setProgress(0);
    setCurrentStep("Submitting request...");

    const formData = new FormData();
    if (mode === "script") {
      if (scriptFile) {
        formData.append("script", scriptFile);
      } else if (scriptText.trim()) {
        formData.append("script", scriptText.trim());
      } else {
        setErrorMsg("Please enter a script or upload a .txt file.");
        return;
      }
    } else {
      if (!audioFile) {
        setErrorMsg("Please select an .mp3 or .wav voice recording.");
        return;
      }
      formData.append("audio", audioFile);
    }

    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_BASE}/generate`, {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Failed to start generation job.");
      }

      setJobId(payload.job_id);
      setJobStatus(payload.status);
      setProgress(5);
      setCurrentStep("Job queued");
      startPolling(payload.job_id);
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="top-nav">
        <div className="brand">
          <span className="brand-badge">PS3</span>
          <div>
            <h1>IncuBrix B-Roll Video Engine</h1>
            <p>Automated Script & Voiceover to Commercial B-Roll Pipeline</p>
          </div>
        </div>
        <div className="stack-pills">
          <span>FastAPI</span>
          <span>Whisper STT</span>
          <span>Pexels + Pixabay</span>
          <span>FFmpeg</span>
        </div>
      </header>

      <main className="main-grid">
        {/* Left Column: Input Controls & Status */}
        <section className="card">
          <h2>1. Select Input Source</h2>
          <div className="mode-tabs">
            <button
              type="button"
              className={mode === "script" ? "tab active" : "tab"}
              onClick={() => setMode("script")}
            >
              Upload Script (.txt / Text)
            </button>
            <button
              type="button"
              className={mode === "audio" ? "tab active" : "tab"}
              onClick={() => setMode("audio")}
            >
              Upload Audio (.mp3 / .wav)
            </button>
          </div>

          <form onSubmit={handleGenerate} className="upload-form">
            {mode === "script" ? (
              <div className="input-group">
                <label htmlFor="scriptTextarea">Plain Text Script</label>
                <textarea
                  id="scriptTextarea"
                  rows={6}
                  value={scriptText}
                  onChange={(e) => setScriptText(e.target.value)}
                  placeholder="Paste narration script here (paragraphs and sentences split scenes automatically)..."
                />
                <div className="file-upload-box">
                  <label htmlFor="scriptFileInput">
                    Or upload a <code>script.txt</code> file:
                  </label>
                  <input
                    id="scriptFileInput"
                    type="file"
                    accept=".txt"
                    onChange={(e) => setScriptFile(e.target.files[0] || null)}
                  />
                </div>
              </div>
            ) : (
              <div className="input-group">
                <div className="file-upload-box highlight">
                  <label htmlFor="audioFileInput">
                    Select Voice Recording (<code>.mp3</code> or <code>.wav</code>)
                  </label>
                  <input
                    id="audioFileInput"
                    type="file"
                    accept=".mp3,.wav,audio/mpeg,audio/wav"
                    onChange={(e) => setAudioFile(e.target.files[0] || null)}
                  />
                  {audioFile && (
                    <p className="file-selected">
                      Selected: <strong>{audioFile.name}</strong> (
                      {(audioFile.size / 1024 / 1024).toFixed(2)} MB)
                    </p>
                  )}
                </div>
              </div>
            )}

            <button
              type="submit"
              className="btn-primary"
              disabled={isSubmitting || jobStatus === "processing" || jobStatus === "queued"}
            >
              {isSubmitting || jobStatus === "processing" || jobStatus === "queued"
                ? "Generating B-Roll Video..."
                : "Generate Video"}
            </button>
          </form>

          {errorMsg && (
            <div className="alert-error" role="alert">
              <strong>Error:</strong> {errorMsg}
            </div>
          )}

          {jobId && (
            <div className="status-panel">
              <div className="status-header">
                <div>
                  <span className="label">Job ID:</span> <code>{jobId}</code>
                </div>
                <span className={`status-badge status-${jobStatus}`}>{jobStatus}</span>
              </div>

              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
              <div className="progress-meta">
                <span>{currentStep}</span>
                <span>{progress}%</span>
              </div>
            </div>
          )}
        </section>

        {/* Right Column: Video Preview, Download Buttons & Scene Timeline */}
        <section className="card">
          <h2>2. Preview & Output Artifacts</h2>
          {!resultData ? (
            <div className="empty-preview">
              <p>
                Submit a script or voiceover recording to preview the synchronized MP4 video,
                download SubRip captions, inspect scene timing, and verify asset licenses.
              </p>
            </div>
          ) : (
            <div className="result-container">
              <video
                className="video-player"
                controls
                autoPlay
                src={`${API_BASE}${resultData.files.video}`}
              />

              <div className="download-grid">
                <a
                  className="btn-download"
                  href={`${API_BASE}${resultData.files.video}`}
                  download="video.mp4"
                >
                  Download Video (.mp4)
                </a>
                <a
                  className="btn-download"
                  href={`${API_BASE}${resultData.files.captions}`}
                  download="captions.srt"
                >
                  Download Captions (.srt)
                </a>
                <a
                  className="btn-download"
                  href={`${API_BASE}${resultData.files.timeline}`}
                  download="timeline.json"
                >
                  Download Timeline (.json)
                </a>
                <a
                  className="btn-download"
                  href={`${API_BASE}${resultData.files.manifest}`}
                  download="manifest.json"
                >
                  Download Manifest (.json)
                </a>
                <a
                  className="btn-download bundle"
                  href={`${API_BASE}${resultData.files.zip}`}
                  download={`job_${jobId}_bundle.zip`}
                >
                  Download Complete ZIP Bundle
                </a>
              </div>

              <div className="metadata-section">
                <h3>Scene Timeline ({resultData.timeline.scenes.length} Scenes)</h3>
                <div className="table-scroll">
                  <table className="meta-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Timing</th>
                        <th>Narration Text</th>
                        <th>Keywords</th>
                        <th>Selected Clip</th>
                      </tr>
                    </thead>
                    <tbody>
                      {resultData.timeline.scenes.map((sc) => (
                        <tr key={sc.scene_id}>
                          <td>{sc.scene_id}</td>
                          <td>
                            {sc.start_time.toFixed(1)}s – {sc.end_time.toFixed(1)}s
                          </td>
                          <td>{sc.text}</td>
                          <td>
                            <div className="kw-list">
                              {sc.keywords.map((kw, i) => (
                                <span key={i} className="kw-chip">
                                  {kw}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td>
                            <code>{sc.selected_clip}</code> ({sc.clip_duration}s)
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="metadata-section">
                <h3>Asset License Manifest</h3>
                <div className="table-scroll">
                  <table className="meta-table">
                    <thead>
                      <tr>
                        <th>Clip</th>
                        <th>Provider</th>
                        <th>Author</th>
                        <th>License</th>
                      </tr>
                    </thead>
                    <tbody>
                      {resultData.manifest.assets.map((asset, idx) => (
                        <tr key={idx}>
                          <td>
                            <code>{asset.clip_name}</code>
                          </td>
                          <td>{asset.provider}</td>
                          <td>{asset.author}</td>
                          <td>{asset.license}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
