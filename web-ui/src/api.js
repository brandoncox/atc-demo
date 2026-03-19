const BASE = import.meta.env.VITE_API_URL || "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export function getShifts({ page = 1, page_size = 10, sort_order = "desc", facility, status } = {}) {
  const params = new URLSearchParams({ page, page_size, sort_order });
  if (facility) params.set("facility", facility);
  if (status) params.set("status", status);
  return request(`/shifts?${params}`);
}

export function getShift(shiftId) {
  return request(`/shift/${shiftId}`);
}

export function deleteShift(shiftId) {
  return request(`/shift/${shiftId}`, { method: "DELETE" });
}

export function transcribe(formData) {
  return request("/transcribe", { method: "POST", body: formData });
}

export function analyzeTranscript(shiftId) {
  return request("/analyze_transcript", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ shift_id: shiftId }),
  });
}
