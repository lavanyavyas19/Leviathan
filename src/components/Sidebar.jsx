// src/components/Sidebar.jsx
//
// FIXES APPLIED:
//   1. uploadError state — shows human-readable message when job status = FAILED
//   2. progress state   — shows percentage during PROCESSING/INGESTING/DETECTING/BUILDING
//   3. Polling interval bumped 1500 ms → 2000 ms (reduces unnecessary server load)
//   4. Upload error cleared on every new import attempt
//   5. Button label reflects detailed stage (Uploading… / Processing… / Detecting… / Building…)
//   6. CRASH FIX: getJob() now returns only metadata (no raw arrays). Downstream
//      data is fetched from paginated endpoints with hard caps:
//        getLiveAlerts  → max 200 records
//        getVesselLogs  → max 200 records
//        getChartData   → 48 pre-aggregated hourly buckets (replaces passing raw alerts)
//   7. Fetches setChartData after DONE so BottomChart never needs raw alert arrays

import React, { useRef, useState, useEffect } from "react";
import {
  importDataset,
  getJob,
  getLiveAlerts,
  getAnomalyReports,
  getVesselLogs,
  getChartData,
} from "../utils/api";

const Sidebar = ({
  activeView,
  setActiveView,
  setDatasetUploaded,
  setJobId,
  setAlerts,
  setVesselLogs,
  setStats,
  setChartData,   // NEW — pre-aggregated chart series for BottomChart
}) => {
  const fileInputRef = useRef(null);

  // ── guards (CRITICAL — prevent duplicate in-flight polls) ──────────────────
  const pollRef        = useRef(null);
  const inFlightRef    = useRef(false);
  const fetchedOnceRef = useRef(false);

  // ── component state ────────────────────────────────────────────────────────
  const [uploading,     setUploading]     = useState(false);
  const [currentJobId,  setCurrentJobId]  = useState(null);
  const [polling,       setPolling]       = useState(false);
  const [uploadError,   setUploadError]   = useState(null);   // shown in UI on FAILED
  const [jobProgress,   setJobProgress]   = useState(0);      // 0-100
  const [jobStage,      setJobStage]      = useState(null);   // PROCESSING / INGESTING / …

  const menuItems = [
    { id: "dashboard",        label: "Dashboard" },
    { id: "vessel-logs",      label: "Vessel Logs" },
    { id: "anomaly-reports",  label: "Anomaly Reports" },
    { id: "audit-logs",       label: "Audit Logs" },
    { id: "settings",         label: "Settings" },
  ];

  // ── Stage → human label ───────────────────────────────────────────────────
  const stageLabel = (stage) => {
    switch (stage) {
      case "PROCESSING":  return "Uploading…";
      case "INGESTING":   return "Ingesting…";
      case "DETECTING":   return "Detecting…";
      case "BUILDING":    return "Building…";
      default:            return "Processing…";
    }
  };

  // ──────────────────────────────────────────────────────────────────────────
  // POLLING  (safe, single interval, terminates on DONE / FAILED / error)
  // ──────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!currentJobId || !polling) return;

    const stopPolling = () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      inFlightRef.current = false;
    };

    const tick = async () => {
      if (inFlightRef.current) return;
      inFlightRef.current = true;

      try {
        const job = await getJob(currentJobId);
        console.log(`[Sidebar] Job ${currentJobId} → ${job.status} (${job.progress ?? "?"}%)`);

        // Update progress bar
        if (job.progress != null) setJobProgress(job.progress);
        if (job.status)           setJobStage(job.status);

        // ── DONE ───────────────────────────────────────────────────────────
        if (job.status === "DONE") {
          stopPolling();
          setPolling(false);
          setJobStage(null);
          setJobProgress(100);
          setDatasetUploaded(true);

          // Fetch downstream data exactly once
          if (fetchedOnceRef.current) return;
          fetchedOnceRef.current = true;

          try {
            // All endpoints are paginated/capped server-side.
            // Hard limits here are a SECOND layer of defence.
            const [alertsData, reportsData, logsData, chartSeries] = await Promise.all([
              getLiveAlerts(currentJobId, { severity: "high,medium", limit: 200 }),
              getAnomalyReports(currentJobId),
              getVesselLogs(currentJobId, { limit: 200 }),   // ← 200, not 500
              getChartData(currentJobId),                     // ← pre-aggregated
            ]);

            // ── Safe timestamp parser ────────────────────────────────────
            const safeDate = (x) => {
              const d = new Date(x);
              return Number.isFinite(d.getTime()) ? d : new Date();
            };

            const transformedAlerts = (alertsData || []).map((a, idx) => ({
              id:           idx + 1,
              type:         a.type,
              vessel:       `MMSI-${a.mmsi}`,
              vesselId:     a.mmsi,
              mmsi:         a.mmsi,
              lat:          a.lat,
              lon:          a.lon,
              timestamp:    safeDate(a.timestamp),
              severity:     a.severity,
              acknowledged: false,
              description:
                a.type === "spoofing"
                  ? `GPS inconsistency (score: ${a.score ?? "N/A"})`
                  : `Loitering detected (cluster: ${a.cluster_size ?? "N/A"})`,
              score:        a.score,
              cluster_size: a.cluster_size,
            }));

            const uniqueMMSIs = new Set((logsData || []).map((l) => l.mmsi));

            setAlerts(transformedAlerts);
            setVesselLogs(logsData || []);
            // Pass pre-aggregated series to BottomChart (avoids sending raw alert arrays)
            setChartData?.(Array.isArray(chartSeries) ? chartSeries : []);
            setStats({
              vesselsTracked:   uniqueMMSIs.size,
              anomaliesDetected: transformedAlerts.length,
              systemHealth:     98.7,
              lastUpdate:       new Date(),
              trends:           { vessels: "stable", anomalies: "stable" },
              anomalyBreakdown: {
                spoofing:  reportsData?.spoofing  ?? 0,
                loitering: reportsData?.loitering ?? 0,
                speed:     reportsData?.speed     ?? 0,
                deviation: reportsData?.deviation ?? 0,
              },
            });

            console.log("[Sidebar] ✅ Data loaded successfully");
          } catch (err) {
            console.error("[Sidebar] ❌ Data fetch failed:", err);
            setUploadError(`Data loaded but details failed to fetch: ${err.message}`);
          }
        }

        // ── FAILED ─────────────────────────────────────────────────────────
        if (job.status === "FAILED") {
          stopPolling();
          setPolling(false);
          setJobStage(null);
          setJobProgress(0);

          const reason = job.error
            ? `Processing failed: ${job.error}`
            : "Processing failed. Please check your file and try again.";

          console.error("[Sidebar] ❌ Job failed:", reason);
          setUploadError(reason);
        }
      } catch (err) {
        console.error("[Sidebar] Polling error:", err);
        stopPolling();
        setPolling(false);
        setJobStage(null);
        setUploadError(`Connection error: ${err.message}`);
      } finally {
        inFlightRef.current = false;
      }
    };

    // Run immediately, then on interval
    tick();
    pollRef.current = setInterval(tick, 2000); // ← bumped from 1500 ms

    return () => stopPolling();
  }, [currentJobId, polling, setDatasetUploaded, setAlerts, setVesselLogs, setStats]);

  // ──────────────────────────────────────────────────────────────────────────
  // UPLOAD HANDLER
  // ──────────────────────────────────────────────────────────────────────────
  const handleFileImport = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    // Reset all state for a fresh run
    setUploading(true);
    setUploadError(null);
    setJobProgress(0);
    setJobStage("PROCESSING");
    setDatasetUploaded(false);
    fetchedOnceRef.current = false;

    // Reset file input so the same file can be re-uploaded if needed
    if (fileInputRef.current) fileInputRef.current.value = "";

    try {
      const result = await importDataset(file);
      console.log("[Sidebar] Upload response:", result);

      if (!result?.job_id) {
        throw new Error("Server did not return a job_id. Check backend logs.");
      }

      setCurrentJobId(result.job_id);
      setJobId?.(result.job_id);
      setPolling(true);
    } catch (err) {
      console.error("[Sidebar] Upload failed:", err);
      setUploadError(`Upload failed: ${err.message}`);
      setJobStage(null);
    } finally {
      setUploading(false);
    }
  };

  // ──────────────────────────────────────────────────────────────────────────
  // DERIVED UI STATE
  // ──────────────────────────────────────────────────────────────────────────
  const isBusy      = uploading || polling;
  const buttonLabel = uploading
    ? "Uploading…"
    : polling
    ? stageLabel(jobStage)
    : "Import Dataset";

  // ──────────────────────────────────────────────────────────────────────────
  // RENDER
  // ──────────────────────────────────────────────────────────────────────────
  return (
    <div className="w-64 bg-slate-800/50 backdrop-blur-lg border-r border-cyan-500/20 p-4 flex flex-col">

      {/* ── Import button + progress ────────────────────────────────────── */}
      <div className="mb-6">
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isBusy}
          className={`w-full px-4 py-3 rounded-lg border transition-all ${
            isBusy
              ? "bg-slate-700/40 text-gray-400 border-slate-600/40 cursor-not-allowed"
              : "bg-gradient-to-r from-emerald-600/30 to-teal-600/30 text-emerald-400 border-emerald-500/30 hover:from-emerald-600/50 hover:to-teal-600/50"
          }`}
        >
          {buttonLabel}
        </button>

        {/* Progress bar — visible while polling */}
        {polling && (
          <div className="mt-2">
            <div className="flex justify-between text-xs text-gray-400 mb-1">
              <span>{jobStage ?? "Processing"}</span>
              <span>{jobProgress}%</span>
            </div>
            <div className="w-full bg-slate-700/50 rounded-full h-1.5">
              <div
                className="bg-gradient-to-r from-cyan-500 to-teal-400 h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${jobProgress}%` }}
              />
            </div>
          </div>
        )}

        {/* Error message — visible when job failed or upload errored */}
        {uploadError && (
          <div className="mt-2 p-2 bg-red-900/30 border border-red-500/40 rounded-lg">
            <div className="flex items-start space-x-2">
              <svg
                className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <p className="text-xs text-red-300 leading-relaxed break-words">
                {uploadError}
              </p>
            </div>
            <button
              onClick={() => setUploadError(null)}
              className="mt-1 text-xs text-red-400/70 hover:text-red-300 underline"
            >
              Dismiss
            </button>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept=".json,.csv,.csv.gz,.gz"
          onChange={handleFileImport}
          className="hidden"
        />
      </div>

      {/* ── Navigation ──────────────────────────────────────────────────── */}
      <nav className="space-y-2 flex-1">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveView(item.id)}
            className={`w-full px-4 py-3 rounded-lg text-left transition-all ${
              activeView === item.id
                ? "bg-cyan-600/30 border border-cyan-500/50 text-cyan-300"
                : "hover:bg-slate-700/50 text-gray-300"
            }`}
          >
            {item.label}
          </button>
        ))}
      </nav>
    </div>
  );
};

export default Sidebar;
