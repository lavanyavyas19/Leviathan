import React, { useRef, useState, useEffect } from "react";
import {
  importDataset,
  getJob,
  getLiveAlerts,
  getAnomalyReports,
  getVesselLogs,
} from "../utils/api";

const Sidebar = ({
  activeView,
  setActiveView,
  setDatasetUploaded,
  setJobId,
  setAlerts,
  setVesselLogs,
  setStats,
}) => {
  const fileInputRef = useRef(null);

  // ---- guards (CRITICAL) ----
  const pollRef = useRef(null);
  const inFlightRef = useRef(false);
  const fetchedOnceRef = useRef(false);

  const [uploading, setUploading] = useState(false);
  const [currentJobId, setCurrentJobId] = useState(null);
  const [polling, setPolling] = useState(false);

  const menuItems = [
    { id: "dashboard", label: "Dashboard" },
    { id: "vessel-logs", label: "Vessel Logs" },
    { id: "anomaly-reports", label: "Anomaly Reports" },
    { id: "audit-logs", label: "Audit Logs" },
    { id: "settings", label: "Settings" },
  ];

  // ------------------------------------------------
  // POLLING (SAFE, SINGLE, DONE-ONCE)
  // ------------------------------------------------
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
        console.log(`Job ${currentJobId} status:`, job.status);

        if (job.status === "DONE") {
          stopPolling();
          setPolling(false);
          setDatasetUploaded(true);

          // fetch ONLY ONCE
          if (fetchedOnceRef.current) return;
          fetchedOnceRef.current = true;

          try {
            const [alertsData, reportsData, logsData] = await Promise.all([
              // 🔑 high + medium alerts
              getLiveAlerts(currentJobId, {
                severity: "high,medium",
                limit: 200,
              }),
              getAnomalyReports(currentJobId),
              getVesselLogs(currentJobId, { limit: 500 }),
            ]);

            // ✅ NECESSARY: safe timestamp parser (prevents Invalid Date breaking sorting/keying)
            const safeDate = (x) => {
              const d = new Date(x);
              return Number.isFinite(d.getTime()) ? d : new Date();
            };

            const transformedAlerts = (alertsData || []).map((a, idx) => ({
              id: idx + 1,
              type: a.type,
              vessel: `MMSI-${a.mmsi}`,
              vesselId: a.mmsi,
              mmsi: a.mmsi,
              lat: a.lat,
              lon: a.lon,
              timestamp: safeDate(a.timestamp), // ✅ FIX
              severity: a.severity,
              acknowledged: false,
              description:
                a.type === "spoofing"
                  ? `GPS inconsistency (score: ${a.score ?? "N/A"})`
                  : `Loitering detected (cluster: ${a.cluster_size ?? "N/A"})`,
              score: a.score,
              cluster_size: a.cluster_size,
            }));

            const uniqueMMSIs = new Set((logsData || []).map((l) => l.mmsi));

            const anomalyBreakdown = transformedAlerts.reduce((acc, al) => {
              acc[al.type] = (acc[al.type] || 0) + 1;
              return acc;
            }, {});

            setAlerts(transformedAlerts);
            setVesselLogs(logsData || []);
            setStats({
              vesselsTracked: uniqueMMSIs.size,
              anomaliesDetected: transformedAlerts.length,
              systemHealth: 98.7,
              lastUpdate: new Date(),
              trends: { vessels: "stable", anomalies: "stable" },
              anomalyBreakdown: {
                spoofing: reportsData?.spoofing ?? anomalyBreakdown.spoofing ?? 0,
                loitering: reportsData?.loitering ?? anomalyBreakdown.loitering ?? 0,
                speed: reportsData?.speed ?? 0,
                deviation: reportsData?.deviation ?? 0,
              },
            });

            console.log("✅ Data loaded");
          } catch (err) {
            console.error("❌ Data fetch failed:", err);
          }
        }

        if (job.status === "FAILED") {
          stopPolling();
          setPolling(false);
          console.error("❌ Job failed");
        }
      } catch (err) {
        console.error("Polling error:", err);
        stopPolling();
        setPolling(false);
      } finally {
        inFlightRef.current = false;
      }
    };

    // run immediately + interval
    tick();
    pollRef.current = setInterval(tick, 1500);

    return () => stopPolling();
  }, [currentJobId, polling, setDatasetUploaded, setAlerts, setVesselLogs, setStats]);

  // ------------------------------------------------
  // UPLOAD
  // ------------------------------------------------
  const handleFileImport = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploading(true);
    setDatasetUploaded(false);
    fetchedOnceRef.current = false;

    try {
      const result = await importDataset(file);
      console.log("Upload response:", result);

      setCurrentJobId(result.job_id);
      setJobId?.(result.job_id);
      setPolling(true);
    } catch (err) {
      console.error("Upload failed:", err);
    } finally {
      setUploading(false);
    }
  };

  // ------------------------------------------------
  // UI
  // ------------------------------------------------
  return (
    <div className="w-64 bg-slate-800/50 backdrop-blur-lg border-r border-cyan-500/20 p-4 flex flex-col">
      <div className="mb-6">
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading || polling}
          className="w-full px-4 py-3 rounded-lg border bg-gradient-to-r from-emerald-600/30 to-teal-600/30 text-emerald-400"
        >
          {uploading || polling ? "Processing..." : "Import Dataset"}
        </button>

        <input
          ref={fileInputRef}
          type="file"
          accept=".json,.csv"
          onChange={handleFileImport}
          className="hidden"
        />
      </div>

      <nav className="space-y-2 flex-1">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveView(item.id)}
            className={`w-full px-4 py-3 rounded-lg ${
              activeView === item.id
                ? "bg-cyan-600/30 border border-cyan-500/50"
                : "hover:bg-slate-700/50"
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
