/**
 * API helper functions for Leviathan backend pipeline
 * Uses relative URLs so Vite proxy handles routing
 * Backend base: http://127.0.0.1:8000
 */

/* ----------------------------------------
   IMPORT DATASET
----------------------------------------- */
export async function importDataset(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/import", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: "Upload failed",
    }));
    throw new Error(error.detail || "Upload failed");
  }

  return response.json(); // { job_id, status }
}

/* ----------------------------------------
   JOB STATUS (POLLING)
----------------------------------------- */
export async function getJob(jobId) {
  const response = await fetch(`/api/jobs/${jobId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: "Failed to fetch job",
    }));
    throw new Error(error.detail || "Failed to fetch job");
  }

  return response.json(); // { status, live_alerts?, vessel_logs?, anomaly_reports? }
}

/* ----------------------------------------
   LIVE ALERTS
   Backend returns ARRAY
----------------------------------------- */
export async function getLiveAlerts(jobId, options = {}) {
  const params = new URLSearchParams();

  // optional filters
  if (options.severity) params.append("severity", options.severity);
  if (options.limit) params.append("limit", options.limit);

  const query = params.toString();
  const url = query
    ? `/api/jobs/${jobId}/live-alerts?${query}`
    : `/api/jobs/${jobId}/live-alerts`;

  const response = await fetch(url);

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: "Failed to fetch live alerts",
    }));
    throw new Error(error.detail || "Failed to fetch live alerts");
  }

  const data = await response.json();
  return Array.isArray(data) ? data : [];
}

/* ----------------------------------------
   ANOMALY REPORTS
   Backend returns OBJECT
----------------------------------------- */
export async function getAnomalyReports(jobId) {
  const response = await fetch(`/api/jobs/${jobId}/anomaly-reports`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: "Failed to fetch anomaly reports",
    }));
    throw new Error(error.detail || "Failed to fetch anomaly reports");
  }

  return response.json(); 
  // {
  //   total,
  //   spoofing,
  //   loitering,
  //   speed,
  //   deviation
  // }
}

/* ----------------------------------------
   VESSEL LOGS
   Backend returns ARRAY
----------------------------------------- */
export async function getVesselLogs(jobId, options = {}) {
  const params = new URLSearchParams();

  if (options.limit) params.append("limit", options.limit);

  const query = params.toString();
  const url = query
    ? `/api/jobs/${jobId}/vessel-logs?${query}`
    : `/api/jobs/${jobId}/vessel-logs`;

  const response = await fetch(url);

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: "Failed to fetch vessel logs",
    }));
    throw new Error(error.detail || "Failed to fetch vessel logs");
  }

  const data = await response.json();
  return Array.isArray(data) ? data : [];
}
