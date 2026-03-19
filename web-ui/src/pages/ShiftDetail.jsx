import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getShift, analyzeTranscript } from "../api";

function MetaItem({ label, value }) {
  return (
    <div className="summary-item">
      <span className="label">{label}</span>
      <span className="value">{value || "—"}</span>
    </div>
  );
}

function StatusBadge({ status }) {
  if (status === "analyzed") return <span className="badge badge-analyzed">✓ Analyzed</span>;
  if (status === "analyzing") return <span className="badge badge-analyzing">⟳ Analyzing</span>;
  return <span className="badge badge-transcribed">○ Transcribed</span>;
}

export default function ShiftDetail() {
  const { shiftId } = useParams();
  const navigate = useNavigate();

  const [shift, setShift] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [tab, setTab] = useState("analysis");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await getShift(shiftId);
      setShift(data);
      if (data.status !== "analyzed") setTab("transcript");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [shiftId]);

  async function handleAnalyze() {
    setAnalyzing(true);
    setError(null);
    try {
      await analyzeTranscript(shiftId);
      await load();
      setTab("analysis");
    } catch (e) {
      setError(e.message);
    } finally {
      setAnalyzing(false);
    }
  }

  if (loading) {
    return (
      <div className="page" style={{ textAlign: "center", paddingTop: 80 }}>
        <span className="spinner" style={{ width: 32, height: 32, borderWidth: 3 }} />
        <p className="text-muted mt-16">Loading shift…</p>
      </div>
    );
  }

  if (error && !shift) {
    return (
      <div className="page">
        <button className="btn btn-ghost btn-sm" onClick={() => navigate("/")}>← Back</button>
        <div className="alert alert-error mt-16">{error}</div>
      </div>
    );
  }

  const createdAt = shift?.created_at
    ? new Date(shift.created_at).toLocaleString()
    : "—";

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header">
        <div className="flex items-center gap-12">
          <button className="btn btn-ghost btn-sm" onClick={() => navigate("/")}>← Back to Shifts</button>
          <div>
            <h2>Shift Report: {shift?.controller_id || "—"}</h2>
            <span className="text-muted text-sm">{shift?.facility || "Unknown Facility"} · {shift?.position || "—"}</span>
          </div>
        </div>
        <div className="flex gap-8 items-center">
          <StatusBadge status={shift?.status} />
          {shift?.status !== "analyzed" && (
            <button className="btn btn-primary" onClick={handleAnalyze} disabled={analyzing}>
              {analyzing ? <><span className="spinner" /> Analyzing…</> : "Analyze Shift"}
            </button>
          )}
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {/* Summary card */}
      <div className="card" style={{ marginBottom: 20 }}>
        <p className="section-title">📊 Summary</p>
        <div className="summary-grid">
          <MetaItem label="Controller" value={shift?.controller_id} />
          <MetaItem label="Facility" value={shift?.facility} />
          <MetaItem label="Position" value={shift?.position} />
          <MetaItem label="Schedule" value={shift?.schedule_type} />
          <MetaItem label="Start Time" value={shift?.start_time} />
          <MetaItem label="End Time" value={shift?.end_time} />
          <MetaItem label="Avg Traffic" value={shift?.traffic_count_avg} />
          <MetaItem label="Language" value={shift?.language} />
          <MetaItem label="Submitted" value={createdAt} />
          <MetaItem label="Whisper Model" value={shift?.model} />
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        <button
          className={`tab ${tab === "analysis" ? "active" : ""}`}
          onClick={() => setTab("analysis")}
        >
          📋 Analysis
        </button>
        <button
          className={`tab ${tab === "transcript" ? "active" : ""}`}
          onClick={() => setTab("transcript")}
        >
          🎙️ Transcript
        </button>
      </div>

      {/* Analysis tab */}
      {tab === "analysis" && (
        <div className="card">
          {shift?.analysis ? (
            <pre className="analysis-body">{shift.analysis}</pre>
          ) : (
            <div style={{ textAlign: "center", padding: "40px 0", color: "var(--muted)" }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>📋</div>
              <p>This shift has not been analyzed yet.</p>
              <button
                className="btn btn-primary mt-16"
                onClick={handleAnalyze}
                disabled={analyzing}
              >
                {analyzing ? <><span className="spinner" /> Analyzing…</> : "Run Analysis"}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Transcript tab */}
      {tab === "transcript" && (
        <div className="card">
          <p className="section-title">Full Transcript</p>
          {shift?.transcription ? (
            <div className="transcript-block">{shift.transcription}</div>
          ) : (
            <p className="text-muted">No transcription available.</p>
          )}
        </div>
      )}
    </div>
  );
}
