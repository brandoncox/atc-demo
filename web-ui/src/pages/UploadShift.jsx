import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { transcribe } from "../api";

const POSITIONS = ["Twr", "App", "Dep", "Gnd", "Del", "ATIS", "En Route", "Other"];
const SCHEDULE_TYPES = ["2-2-1", "4-on-4-off", "5-on-2-off", "Other"];

export default function UploadShift() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const [fields, setFields] = useState({
    shift_id: "",
    controller_id: "",
    facility: "",
    position: "",
    schedule_type: "",
    start_time: "",
    end_time: "",
    traffic_count_avg: "",
    original_file: "",
    language: "",
    prompt: "",
  });

  function setField(e) {
    setFields((f) => ({ ...f, [e.target.name]: e.target.value }));
  }

  function onFileChange(e) {
    const picked = e.target.files?.[0];
    if (picked) setFile(picked);
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) setFile(dropped);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!file) { setError("Please select an audio file."); return; }

    setSubmitting(true);
    setError(null);
    setSuccess(null);

    const fd = new FormData();
    fd.append("file", file);
    Object.entries(fields).forEach(([k, v]) => {
      if (v !== "") fd.append(k, v);
    });

    try {
      const result = await transcribe(fd);
      setSuccess(`Shift transcribed successfully. Shift ID: ${result.shift_id || result._id}`);
      if (result.shift_id) {
        setTimeout(() => navigate(`/shift/${result.shift_id}`), 1500);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div className="flex items-center gap-12">
          <button className="btn btn-ghost btn-sm" onClick={() => navigate("/")}>← Back</button>
          <h2>Upload Shift Audio</h2>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        {/* Drop zone */}
        <div className="card" style={{ marginBottom: 20 }}>
          <p className="section-title">Audio File</p>
          <div
            className={`dropzone ${dragging ? "active" : ""}`}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            <input ref={fileInputRef} type="file" accept="audio/*,.mp3,.wav,.m4a,.ogg,.flac" onChange={onFileChange} />
            <div className="icon">🎙️</div>
            <div>Drag & drop an audio file here, or click to browse</div>
            <div className="hint">Supports MP3, WAV, M4A, OGG, FLAC</div>
            {file && <div className="file-name">✓ {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)</div>}
          </div>
        </div>

        {/* Shift metadata */}
        <div className="card" style={{ marginBottom: 20 }}>
          <p className="section-title">Shift Metadata</p>
          <div className="form-grid">
            <div className="field">
              <label>Shift ID</label>
              <input name="shift_id" value={fields.shift_id} onChange={setField} placeholder="shift_20250624_0800" />
            </div>
            <div className="field">
              <label>Controller ID</label>
              <input name="controller_id" value={fields.controller_id} onChange={setField} placeholder="CTR-123" />
            </div>
            <div className="field">
              <label>Facility</label>
              <input name="facility" value={fields.facility} onChange={setField} placeholder="KLAX" />
            </div>
            <div className="field">
              <label>Position</label>
              <select name="position" value={fields.position} onChange={setField}>
                <option value="">Select position…</option>
                {POSITIONS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Schedule Type</label>
              <select name="schedule_type" value={fields.schedule_type} onChange={setField}>
                <option value="">Select schedule…</option>
                {SCHEDULE_TYPES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Avg Traffic Count</label>
              <input
                name="traffic_count_avg"
                type="number"
                min={0}
                value={fields.traffic_count_avg}
                onChange={setField}
                placeholder="15"
              />
            </div>
            <div className="field">
              <label>Start Time</label>
              <input
                name="start_time"
                type="datetime-local"
                value={fields.start_time}
                onChange={setField}
              />
            </div>
            <div className="field">
              <label>End Time</label>
              <input
                name="end_time"
                type="datetime-local"
                value={fields.end_time}
                onChange={setField}
              />
            </div>
            <div className="field">
              <label>Original Filename</label>
              <input
                name="original_file"
                value={fields.original_file}
                onChange={setField}
                placeholder="recording-2025-06-24.mp3"
              />
            </div>
          </div>
        </div>

        {/* Transcription options */}
        <div className="card" style={{ marginBottom: 20 }}>
          <p className="section-title">Transcription Options</p>
          <div className="form-grid">
            <div className="field">
              <label>Language</label>
              <input name="language" value={fields.language} onChange={setField} placeholder="en" />
            </div>
            <div className="field" style={{ gridColumn: "span 2" }}>
              <label>Prompt (optional context)</label>
              <input
                name="prompt"
                value={fields.prompt}
                onChange={setField}
                placeholder="Air traffic control communication, tower frequency"
              />
            </div>
          </div>
        </div>

        {error && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        <div className="flex gap-8">
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? <><span className="spinner" /> Transcribing…</> : "Upload & Transcribe"}
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => navigate("/")}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
