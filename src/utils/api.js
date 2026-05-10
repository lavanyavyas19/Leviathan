/**
 * api.js — API helper functions for Leviathan backend pipeline
 *
 * CRASH FIX — CRITICAL:
 *   getJob() previously called response.json() on a 50+ MB payload
 *   (the server was returning all live_alerts + vessel_logs inside the
 *   job status response).  Now that job.py strips those arrays from the
 *   status endpoint, the response is a few KB.  This file adds an
 *   additional safety guard that hard-rejects any status response
 *   exceeding 1 MB so a backend regression never crashes the tab again.
 *
 * NEW ENDPOINTS:
 *   getMapPoints()  — sampled geo positions for map rendering (≤ 500 pts)
 *   getChartData()  — pre-aggregated hourly time series for BottomChart
 *
 * ALL ENDPOINTS:
 *   - AbortController timeout (120 s upload, 10 s poll, 15 s data)
 *   - clearTimeout() in finally — no timer leaks
 *   - Structured error objects include HTTP status code
 *
 * Uses relative URLs → Vite proxy routes /api/* → http://127.0.0.1:8000
 */

// ─────────────────────────────────────────────────────────────────────────────
// INTERNAL HELPERS
// ─────────────────────────────────────────────────────────────────────────────

/** Create a self-cancelling timeout.  Always call clear() in finally. */
function makeTimeout(ms) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), ms);
  return { signal: controller.signal, clear: () => clearTimeout(id) };
}

/** Parse error body, fall back to a plain message. */
async function parseError(response, fallback) {
  try {
    const body = await response.json();
    return body?.detail || body?.message || fallback;
  } catch {
    return fallback;
  }
}

/**
 * Parse response as text first, enforce a size cap, then parse JSON.
 * Prevents a misbehaving backend from sending a 50 MB payload that
 * Chrome has to parse and React has to store.
 *
 * @param {Response} response
 * @param {number}   maxBytes   — reject if text exceeds this (default 2 MB)
 */
async function safeJson(response, maxBytes = 2 * 1024 * 1024) {
  const text = await response.text();
  if (text.length > maxBytes) {
    const mb = (text.length / 1024 / 1024).toFixed(1);
    throw new Error(
      `Response too large (${mb} MB). ` +
      `This usually means the backend returned raw arrays in a status endpoint. ` +
      `Check that job.py is stripping live_alerts / vessel_logs from GET /jobs/{id}.`
    );
  }
  return JSON.parse(text);
}


// ─────────────────────────────────────────────────────────────────────────────
// IMPORT DATASET
// ─────────────────────────────────────────────────────────────────────────────

/**
 * POST /api/import
 * Timeout 120 s — large file uploads need the headroom.
 * @param {File} file
 * @returns {{ job_id: string, status: string }}
 */
export async function importDataset(file) {
  const { signal, clear } = makeTimeout(120_000);
  try {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch("/api/import", { method: "POST", body: formData, signal });

    if (!response.ok) {
      const msg = await parseError(response, "Upload failed");
      const err = new Error(msg);
      err.status = response.status;
      throw err;
    }

    return response.json();  // { job_id, status } — tiny payload, no size guard needed
  } catch (err) {
    if (err.name === "AbortError")
      throw new Error("Upload timed out after 2 minutes. Try a smaller file or check your connection.");
    throw err;
  } finally {
    clear();
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// JOB STATUS  (polling)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * GET /api/jobs/:jobId
 * Returns ONLY status/progress metadata — heavy arrays are stripped server-side.
 * Timeout 10 s.  Size guard 1 MB (a valid status response is < 2 KB).
 *
 * @param {string} jobId
 * @returns {{ status: string, progress: number, summary?: object, error?: string }}
 */
export async function getJob(jobId) {
  const { signal, clear } = makeTimeout(10_000);
  try {
    const response = await fetch(`/api/jobs/${jobId}`, { signal });

    if (!response.ok) {
      const msg = await parseError(response, "Failed to fetch job");
      const err = new Error(msg);
      err.status = response.status;
      throw err;
    }

    // ── SIZE GUARD ───────────────────────────────────────────────────────────
    // A valid status payload is < 2 KB.  If we receive > 1 MB the backend is
    // still sending raw arrays — reject before Chrome OOMs.
    return await safeJson(response, 1 * 1024 * 1024);
  } catch (err) {
    if (err.name === "AbortError")
      throw new Error("Job status request timed out (10 s). Server may be busy.");
    throw err;
  } finally {
    clear();
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// LIVE ALERTS  (paginated array)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * GET /api/jobs/:jobId/live-alerts
 * Server hard-caps at 200 records.
 * Timeout 15 s.
 *
 * @param {string} jobId
 * @param {{ severity?: string, limit?: number, offset?: number }} [options]
 * @returns {Array}
 */
export async function getLiveAlerts(jobId, options = {}) {
  const { signal, clear } = makeTimeout(15_000);
  try {
    const params = new URLSearchParams();
    if (options.severity) params.append("severity", options.severity);
    if (options.limit)    params.append("limit",    Math.min(options.limit, 200));
    if (options.offset)   params.append("offset",   options.offset);

    const query = params.toString();
    const url   = query
      ? `/api/jobs/${jobId}/live-alerts?${query}`
      : `/api/jobs/${jobId}/live-alerts`;

    const response = await fetch(url, { signal });

    if (!response.ok) {
      const msg = await parseError(response, "Failed to fetch live alerts");
      const err = new Error(msg);
      err.status = response.status;
      throw err;
    }

    // 200 records × ~100 bytes = ~20 KB; guard at 5 MB just in case
    const data = await safeJson(response, 5 * 1024 * 1024);
    return Array.isArray(data) ? data : [];
  } catch (err) {
    if (err.name === "AbortError")
      throw new Error("Live alerts request timed out (15 s).");
    throw err;
  } finally {
    clear();
  }
}

/**
 * POST /api/audit-logs/alert-action
 * Fire-and-forget — silently swallows errors so UI is never blocked.
 * Logs ALERT_ACK or ALERT_DISMISSED to the tamper-evident audit chain.
 *
 * @param {{ action: string, alertId: string, vesselId?: number|null,
 *            timestamp?: Date|string|null, user?: string, details?: string|null }} opts
 */
export async function logAlertAction({ action, alertId, vesselId, timestamp, user = "operator", details } = {}) {
  const { signal, clear } = makeTimeout(10_000);
  try {
    const ts =
      timestamp instanceof Date
        ? timestamp.toISOString()
        : timestamp ?? new Date().toISOString();

    await fetch("/api/audit-logs/alert-action", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        alert_id:  alertId  ?? "",
        vessel_id: vesselId ?? null,
        timestamp: ts,
        user,
        details:   details  ?? null,
      }),
      signal,
    });
    // Response is intentionally ignored — best-effort audit write
  } catch {
    // Network error or abort — silently ignore so UI never crashes
  } finally {
    clear();
  }
}

export async function getAuditLogs({ limit = 200, offset = 0, event_type } = {}) {
  const { signal, clear } = makeTimeout(15_000);
  try {
    const params = new URLSearchParams();
    params.append("limit", limit);
    params.append("offset", offset);
    if (event_type) params.append("event_type", event_type);

    const response = await fetch(`/api/audit-logs?${params.toString()}`, { signal });

    if (!response.ok) {
      const msg = await parseError(response, "Failed to fetch audit logs");
      const err = new Error(msg);
      err.status = response.status;
      throw err;
    }

    return await safeJson(response, 2 * 1024 * 1024);
  } catch (err) {
    if (err.name === "AbortError") {
      throw new Error("Audit logs request timed out (15 s).");
    }
    throw err;
  } finally {
    clear();
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// ANOMALY REPORTS  (counts object)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * GET /api/jobs/:jobId/anomaly-reports
 * Returns { total, spoofing, loitering, speed, deviation } — no raw records.
 * Timeout 15 s.
 *
 * @param {string} jobId
 * @returns {{ total: number, spoofing: number, loitering: number, speed: number, deviation: number }}
 */
export async function getAnomalyReports(jobId) {
  const { signal, clear } = makeTimeout(15_000);
  try {
    const response = await fetch(`/api/jobs/${jobId}/anomaly-reports`, { signal });

    if (!response.ok) {
      const msg = await parseError(response, "Failed to fetch anomaly reports");
      const err = new Error(msg);
      err.status = response.status;
      throw err;
    }

    return response.json();  // tiny counts object
  } catch (err) {
    if (err.name === "AbortError")
      throw new Error("Anomaly reports request timed out (15 s).");
    throw err;
  } finally {
    clear();
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// VESSEL LOGS  (paginated array)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * GET /api/jobs/:jobId/vessel-logs
 * Server hard-caps at 500 records.
 * Timeout 15 s.
 *
 * @param {string} jobId
 * @param {{ limit?: number, offset?: number }} [options]
 * @returns {Array}
 */
export async function getVesselLogs(jobId, options = {}) {
  const { signal, clear } = makeTimeout(15_000);
  try {
    const params = new URLSearchParams();
    if (options.limit)  params.append("limit",  Math.min(options.limit, 500));
    if (options.offset) params.append("offset", options.offset);

    const query = params.toString();
    const url   = query
      ? `/api/jobs/${jobId}/vessel-logs?${query}`
      : `/api/jobs/${jobId}/vessel-logs`;

    const response = await fetch(url, { signal });

    if (!response.ok) {
      const msg = await parseError(response, "Failed to fetch vessel logs");
      const err = new Error(msg);
      err.status = response.status;
      throw err;
    }

    // 500 records × ~150 bytes = ~75 KB; guard at 5 MB
    const data = await safeJson(response, 5 * 1024 * 1024);
    return Array.isArray(data) ? data : [];
  } catch (err) {
    if (err.name === "AbortError")
      throw new Error("Vessel logs request timed out (15 s).");
    throw err;
  } finally {
    clear();
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// MAP POINTS  — NEW
// ─────────────────────────────────────────────────────────────────────────────

/**
 * GET /api/jobs/:jobId/map-points
 * Returns up to 500 sampled vessel positions.
 * Anomalous vessels are always included; normal vessels fill remaining slots.
 * Timeout 15 s.
 *
 * @param {string} jobId
 * @param {{ limit?: number }} [options]
 * @returns {Array<{ mmsi, lat, lon, spoofing_flag, loitering_flag, vessel_name, status }>}
 */
export async function getMapPoints(jobId, options = {}) {
  const { signal, clear } = makeTimeout(15_000);
  try {
    const params = new URLSearchParams();
    if (options.limit) params.append("limit", Math.min(options.limit, 500));

    const query = params.toString();
    const url   = query
      ? `/api/jobs/${jobId}/map-points?${query}`
      : `/api/jobs/${jobId}/map-points`;

    const response = await fetch(url, { signal });

    if (!response.ok) {
      const msg = await parseError(response, "Failed to fetch map points");
      const err = new Error(msg);
      err.status = response.status;
      throw err;
    }

    // 500 pts × 7 fields × ~20 bytes = ~70 KB; guard at 2 MB
    const data = await safeJson(response, 2 * 1024 * 1024);
    return Array.isArray(data) ? data : [];
  } catch (err) {
    if (err.name === "AbortError")
      throw new Error("Map points request timed out (15 s).");
    throw err;
  } finally {
    clear();
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// CHART DATA  — NEW
// ─────────────────────────────────────────────────────────────────────────────

/**
 * GET /api/jobs/:jobId/chart-data
 * Returns pre-aggregated hourly time series (≤ 48 buckets).
 * Timeout 15 s.
 *
 * @param {string} jobId
 * @returns {Array<{ time: string, spoofing: number, loitering: number, other: number, total: number }>}
 */
export async function getChartData(jobId) {
  const { signal, clear } = makeTimeout(15_000);
  try {
    const response = await fetch(`/api/jobs/${jobId}/chart-data`, { signal });

    if (!response.ok) {
      const msg = await parseError(response, "Failed to fetch chart data");
      const err = new Error(msg);
      err.status = response.status;
      throw err;
    }

    // 48 buckets × 5 fields = ~2 KB; guard at 500 KB
    const data = await safeJson(response, 500 * 1024);
    return Array.isArray(data) ? data : [];
  } catch (err) {
    if (err.name === "AbortError")
      throw new Error("Chart data request timed out (15 s).");
    throw err;
  } finally {
    clear();
  }
}
