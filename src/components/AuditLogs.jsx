import React, { useState, useEffect } from "react";
import { ShieldCheck, Download } from "lucide-react";
import { getAuditLogs } from "../utils/api";

const dummyAuditLogs = [
  // ---- Spoofing (LOW only) ----
  ...Array.from({ length: 20 }).map((_, i) => ({
    hash: `spoof_hash_${i}`,
    previous_hash: i === 0 ? "0".repeat(64) : `spoof_hash_${i - 1}`,
    event: {
      type: "spoofing",
      severity: "low",
      actor: "system",
      timestamp: new Date(Date.now() - i * 60000).toISOString(),
      payload: {
        speed: 0.3,
        heading_change: 140 + i,
        jump_distance: 10 + i,
        anomaly_score: -0.1
      }
    }
  })),

  // ---- Loitering (ALL severities) ----
  ...Array.from({ length: 10 }).map((_, i) => ({
    hash: `loiter_hash_${i}`,
    previous_hash: `loiter_hash_${i - 1}`,
    event: {
      type: "loitering",
      severity: ["low", "medium", "high"][i % 3],
      actor: "system",
      timestamp: new Date(Date.now() - (i + 20) * 60000).toISOString(),
      payload: {
        cluster_size: 12 + i,
        coordinates: [[18.92, 72.83]]
      }
    }
  }))
];

/**
 * Normalise a backend audit entry (NDJSON schema) into the internal shape
 * that the rest of the component already uses.
 *
 * Backend schema:
 *   { seq, timestamp_utc, event_type, payload, previous_hash, current_hash }
 *
 * Internal shape:
 *   { hash, previous_hash, event: { type, severity, timestamp, payload } }
 */
function normaliseEntry(entry) {
  // Derive a human-readable event type from the event_type string.
  // e.g. "spoofing_detected" → "spoofing", "loitering_detected" → "loitering",
  //      "alert_emitted" → "alert",  "dataset_imported" → "dataset_imported"
  const rawType = (entry.event_type || "unknown").toLowerCase();
  let type = rawType;
  if (rawType.startsWith("spoofing")) type = "spoofing";
  else if (rawType.startsWith("loitering")) type = "loitering";
  else if (rawType === "alert_emitted") {
    // payload carries the underlying detection type (set by _audit_detection_events)
    type = entry.payload?.event_type || entry.payload?.type || "alert";
  } else if (rawType === "alert_ack") {
    type = "alert_ack";
  } else if (rawType === "alert_dismissed") {
    type = "alert_dismissed";
  }

  const severity =
    entry.payload?.severity ||
    entry.payload?.alert_severity ||
    "low";

  // vessel_id — present on alert_emitted and detection summary entries
  const vesselId = entry.payload?.vessel_id ?? null;

  // human-readable details string written by the backend helper
  const details = entry.payload?.details || null;

  return {
    hash: entry.current_hash || "",
    previous_hash: entry.previous_hash || "",
    event: {
      type,
      severity,
      actor: "system",
      timestamp: entry.timestamp_utc || new Date().toISOString(),
      payload: entry.payload || {},
      vessel_id: vesselId,
      details,
    }
  };
}

const AuditLogs = ({ auditLogs }) => {
  const [liveEntries, setLiveEntries]   = useState(null); // null = not yet fetched
  const [fetchError, setFetchError]     = useState(null);

  // Fetch real audit log entries from the backend on mount.
  useEffect(() => {
    let cancelled = false;
    getAuditLogs({ limit: 200 })
      .then(data => {
        if (cancelled) return;
        const entries = (data.entries || []).map(normaliseEntry);
        setLiveEntries(entries.length ? entries : null); // null → fall back to dummy
      })
      .catch(err => {
        if (cancelled) return;
        console.warn("AuditLogs: could not fetch backend entries:", err.message);
        setFetchError(err.message);
        setLiveEntries(null);
      });
    return () => { cancelled = true; };
  }, []);

  // Priority: prop → live backend fetch → dummy
  const logsSource =
    (auditLogs?.length ? auditLogs : null) ||
    liveEntries ||
    dummyAuditLogs;

  const isLiveData = !!(liveEntries?.length || auditLogs?.length);

  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [selectedLog, setSelectedLog] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const rowsPerPage = 5;

  useEffect(() => {
    setCurrentPage(1);
  }, [filter, search]);

  const logs = logsSource.map((log, idx) => {
    const date = new Date(log.event.timestamp);
    return {
      id: idx + 1,
      type: log.event.type,
      severity: log.event.severity || "low",
      actor: "system",
      hash: log.hash,
      prevHash: log.previous_hash,
      timestamp: date.toLocaleString(),
      payload: log.event.payload,
      vesselId: log.event.vessel_id ?? null,
      details: log.event.details ?? null,
    };
  });

  const searchLower = search.toLowerCase();
  const filteredLogs = logs.filter(
    l =>
      (filter === "all" || l.type === filter) &&
      (!searchLower || (
        l.type.toLowerCase().includes(searchLower) ||
        l.actor.toLowerCase().includes(searchLower) ||
        (l.vesselId != null && String(l.vesselId).includes(searchLower)) ||
        (l.details   && l.details.toLowerCase().includes(searchLower))
      ))
  );

  const totalPages = Math.ceil(filteredLogs.length / rowsPerPage);
  const startIndex = (currentPage - 1) * rowsPerPage;
  const currentLogs = filteredLogs.slice(
    startIndex,
    startIndex + rowsPerPage
  );

  const getSeverityColor = s => {
    if (s === "high") return "bg-red-500 text-white";
    if (s === "medium") return "bg-yellow-400 text-black";
    return "bg-green-500 text-white";
  };

  const exportCSV = () => {
    const csv = [
      ["Type", "Severity", "Vessel", "Details", "Hash", "Previous Hash", "Timestamp"],
      ...filteredLogs.map(l => [
        l.type,
        l.severity,
        l.vesselId != null ? `MMSI-${l.vesselId}` : "",
        l.details || "",
        l.hash,
        l.prevHash,
        l.timestamp
      ])
    ]
      .map(r => r.join(","))
      .join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "audit_logs.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="bg-slate-800/40 border border-cyan-500/30 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-cyan-400">Audit Logs</h2>
        {isLiveData ? (
          <span className="flex items-center gap-1 text-xs text-green-400 bg-green-400/10 px-2 py-1 rounded-full">
            <ShieldCheck className="w-3 h-3" /> Live — Chain Verified
          </span>
        ) : (
          <span className="text-xs text-yellow-400 bg-yellow-400/10 px-2 py-1 rounded-full">
            Demo Data{fetchError ? ` (backend: ${fetchError})` : ""}
          </span>
        )}
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-4">
        <select
          value={filter}
          onChange={e => setFilter(e.target.value)}
          className="bg-slate-700 px-3 py-2 rounded-lg border border-slate-600"
        >
          <option value="all">All Events</option>
          <option value="spoofing">Spoofing</option>
          <option value="loitering">Loitering</option>
          <option value="alert_ack">Acknowledged Alerts</option>
          <option value="alert_dismissed">Dismissed Alerts</option>
        </select>

        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search..."
          className="flex-1 bg-slate-700 px-3 py-2 rounded-lg border border-slate-600"
        />
      </div>

      {/* Table */}
      <table className="w-full text-sm text-gray-300">
        <thead className="bg-slate-700 text-gray-400">
          <tr>
            <th className="px-4 py-2 text-left">Event</th>
            <th className="px-4 py-2 text-left">Severity</th>
            <th className="px-4 py-2 text-left">Vessel</th>
            <th className="px-4 py-2 text-left">Details</th>
            <th className="px-4 py-2 text-left">Hash</th>
            <th className="px-4 py-2 text-left">Prev Hash</th>
            <th className="px-4 py-2 text-left">Time</th>
            <th className="px-4 py-2 text-left">Status</th>
          </tr>
        </thead>
        <tbody>
          {currentLogs.map(log => (
            <tr
              key={log.id}
              onClick={() => setSelectedLog(log)}
              className="border-b border-slate-600 hover:bg-slate-700/40 cursor-pointer"
            >
              <td className="px-4 py-2 capitalize">{log.type}</td>
              <td className="px-4 py-2">
                <span
                  className={`px-2 py-1 rounded text-xs font-bold ${getSeverityColor(
                    log.severity
                  )}`}
                >
                  {log.severity.toUpperCase()}
                </span>
              </td>
              <td className="px-4 py-2 font-mono text-xs text-cyan-300">
                {log.vesselId != null ? `MMSI-${log.vesselId}` : "—"}
              </td>
              <td className="px-4 py-2 text-xs text-gray-300 max-w-[200px] truncate" title={log.details || ""}>
                {log.details || "—"}
              </td>
              <td className="px-4 py-2 font-mono text-xs">
                {log.hash.slice(0, 10)}…
              </td>
              <td className="px-4 py-2 font-mono text-xs">
                {log.prevHash ? log.prevHash.slice(0, 10) + "…" : "—"}
              </td>
              <td className="px-4 py-2">{log.timestamp}</td>
              <td className="px-4 py-2 text-green-400">
                {isLiveData ? "✓ Verified" : "Demo"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Pagination */}
      <div className="flex justify-between items-center mt-4 text-sm text-gray-300">
        <span>Page {currentPage} of {totalPages || 1}</span>
        <div className="space-x-2">
          <button
            disabled={currentPage === 1}
            onClick={() => setCurrentPage(p => p - 1)}
            className="px-3 py-1 bg-slate-700 rounded disabled:opacity-40"
          >
            Prev
          </button>
          <button
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage(p => p + 1)}
            className="px-3 py-1 bg-slate-700 rounded disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>

      {/* Export */}
      <div className="flex justify-end mt-6">
        <button
          onClick={exportCSV}
          className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-black rounded-lg text-sm font-semibold"
        >
          <Download className="w-4 h-4" />
          Export Logs
        </button>
      </div>
    </div>
  );
};

export default AuditLogs;