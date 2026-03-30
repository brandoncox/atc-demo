import { useState, useEffect, useCallback } from "react";
import { useNavigate, Link } from "react-router-dom";
import { getShifts, analyzeTranscript, deleteShift } from "../api";

function StatusBadge({ status }) {
  if (status === "analyzed") return <span className="badge badge-analyzed">✓ Analyzed</span>;
  if (status === "analyzing") return <span className="badge badge-analyzing">⟳ Analyzing</span>;
  return <span className="badge badge-transcribed">○ Transcribed</span>;
}

export default function ShiftList() {
  const navigate = useNavigate();

  const [shifts, setShifts] = useState([]);
  const [meta, setMeta] = useState({ total_shifts: 0, total_pages: 1, current_page: 1 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [analyzing, setAnalyzing] = useState({});

  const [filters, setFilters] = useState({ facility: "", status: "" });
  const [page, setPage] = useState(1);
  const [sortOrder, setSortOrder] = useState("desc");
  const [selected, setSelected] = useState(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getShifts({
        page,
        page_size: 10,
        sort_order: sortOrder,
        facility: filters.facility || undefined,
        status: filters.status || undefined,
      });
      setShifts(data.shifts);
      setMeta(data.metadata);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [page, sortOrder, filters]);

  useEffect(() => { load(); }, [load]);

  function handleFilterChange(e) {
    setFilters((f) => ({ ...f, [e.target.name]: e.target.value }));
    setPage(1);
  }

  function toggleSelect(shiftId) {
    setSelected((s) => {
      const next = new Set(s);
      next.has(shiftId) ? next.delete(shiftId) : next.add(shiftId);
      return next;
    });
  }

  function toggleSelectAll() {
    if (selected.size === shifts.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(shifts.map((s) => s.shift_id).filter(Boolean)));
    }
  }

  async function handleAnalyze(shiftId) {
    setAnalyzing((a) => ({ ...a, [shiftId]: true }));
    try {
      await analyzeTranscript(shiftId);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setAnalyzing((a) => ({ ...a, [shiftId]: false }));
    }
  }

  async function handleBatchAnalyze() {
    const unanalyzed = [...selected].filter((id) => {
      const shift = shifts.find((s) => s.shift_id === id);
      return shift && shift.status !== "analyzed";
    });
    for (const id of unanalyzed) {
      await handleAnalyze(id);
    }
    setSelected(new Set());
  }

  async function handleDelete(shiftId) {
    if (!confirm(`Delete shift ${shiftId}?`)) return;
    try {
      await deleteShift(shiftId);
      await load();
    } catch (e) {
      setError(e.message);
    }
  }

  const unanalyzedSelected = [...selected].filter((id) => {
    const shift = shifts.find((s) => s.shift_id === id);
    return shift && shift.status !== "analyzed";
  });

  return (
    <div className="page">
      <div className="page-header">
        <h2>Select Shift to Analyze</h2>
        {unanalyzedSelected.length > 0 && (
          <button className="btn btn-primary" onClick={handleBatchAnalyze}>
            Batch Analyze Selected ({unanalyzedSelected.length})
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="filters">
        <div className="field">
          <label>Facility</label>
          <input
            name="facility"
            value={filters.facility}
            onChange={handleFilterChange}
            placeholder="e.g. KLAX"
          />
        </div>
        <div className="field">
          <label>Status</label>
          <select name="status" value={filters.status} onChange={handleFilterChange}>
            <option value="">All Statuses</option>
            <option value="transcribed">Transcribed</option>
            <option value="analyzed">Analyzed</option>
          </select>
        </div>
        <div className="field">
          <label>Sort</label>
          <select value={sortOrder} onChange={(e) => { setSortOrder(e.target.value); setPage(1); }}>
            <option value="desc">Newest first</option>
            <option value="asc">Oldest first</option>
          </select>
        </div>
        <button className="btn btn-ghost" onClick={load} disabled={loading}>
          {loading ? <span className="spinner" /> : "Search"}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {/* Table */}
      <div className="card" style={{ padding: 0 }}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: 36 }}>
                  <input
                    type="checkbox"
                    checked={selected.size === shifts.length && shifts.length > 0}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th>Shift ID</th>
                <th>Controller</th>
                <th>Facility</th>
                <th>Position</th>
                <th>Start</th>
                <th>End</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {shifts.length === 0 && !loading && (
                <tr>
                  <td colSpan={9} style={{ textAlign: "center", color: "var(--muted)", padding: "32px" }}>
                    No shifts found.
                  </td>
                </tr>
              )}
              {shifts.map((shift) => (
                <tr key={shift._id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selected.has(shift.shift_id)}
                      onChange={() => toggleSelect(shift.shift_id)}
                      disabled={!shift.shift_id}
                    />
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>
                    {shift.shift_id ? <Link to={`/shift/${shift.shift_id}`}>{shift.shift_id}</Link> : "—"}
                  </td>
                  <td>{shift.controller_id || "—"}</td>
                  <td>{shift.facility || "—"}</td>
                  <td>{shift.position || "—"}</td>
                  <td className="text-muted text-sm">{shift.start_time || "—"}</td>
                  <td className="text-muted text-sm">{shift.end_time || "—"}</td>
                  <td><StatusBadge status={shift.status} /></td>
                  <td>
                    <div className="flex gap-8">
                      {shift.status === "analyzed" ? (
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => navigate(`/shift/${shift.shift_id}`)}
                        >
                          View
                        </button>
                      ) : (
                        <button
                          className="btn btn-primary btn-sm"
                          disabled={!shift.shift_id || analyzing[shift.shift_id]}
                          onClick={() => handleAnalyze(shift.shift_id)}
                        >
                          {analyzing[shift.shift_id] ? <span className="spinner" /> : "Analyze"}
                        </button>
                      )}
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDelete(shift.shift_id)}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      <div className="pagination">
        <span>
          {meta.total_shifts} shift{meta.total_shifts !== 1 ? "s" : ""}
          {meta.total_pages > 1 && ` — page ${meta.current_page} of ${meta.total_pages}`}
        </span>
        <div className="pagination-controls">
          <button
            className="btn btn-ghost btn-sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            ← Prev
          </button>
          <button
            className="btn btn-ghost btn-sm"
            disabled={page >= meta.total_pages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}
