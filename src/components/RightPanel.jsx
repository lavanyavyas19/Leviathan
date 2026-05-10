import React, { useMemo, useState, useEffect } from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { logAlertAction } from "../utils/api";

/**
 * Stable key so ACK/Dismiss works even if list order changes.
 */
function alertKey(a) {
  const d = a?.timestamp instanceof Date ? a.timestamp : new Date(a?.timestamp);
  const ts = Number.isFinite(d.getTime()) ? d.toISOString() : "no-ts";
  return `${a?.type || "unknown"}|${a?.mmsi || a?.vesselId || "no-mmsi"}|${ts}`;
}

function normType(t) {
  const s = String(t || "").toLowerCase();
  if (s.includes("spoof")) return "spoofing";
  if (s.includes("loiter")) return "loitering";
  return "other";
}

const RightPanel = ({
  onAlertClick,
  datasetUploaded,
  alerts: propAlerts = [],
  stats: propStats = null,
}) => {
  // ACK/Dismiss state
  const [ackMap, setAckMap] = useState({});
  const [dismissMap, setDismissMap] = useState({});

  // ✅ UI filters
  const [typeFilter, setTypeFilter] = useState("all"); // all | spoofing | loitering
  const [sevFilter, setSevFilter] = useState({ high: true, medium: true }); // no low
  const [searchQuery, setSearchQuery] = useState(""); // ✅ SEARCH BAR BACK

  useEffect(() => {
    // Optional: reset filters on new dataset upload
    // setTypeFilter("all");
    // setSevFilter({ high: true, medium: true });
    // setAckMap({});
    // setDismissMap({});
    // setSearchQuery("");
  }, [datasetUploaded]);

  const stats = propStats || {
    vesselsTracked: 0,
    anomaliesDetected: propAlerts.length,
    systemHealth: 98.7,
    lastUpdate: new Date(),
    trends: { vessels: "stable", anomalies: "stable" },
    anomalyBreakdown: { spoofing: 0, loitering: 0, speed: 0, deviation: 0 },
  };

  const getTrendIcon = (trend) => {
    switch (trend) {
      case "up":
        return <TrendingUp className="w-4 h-4 text-green-400" />;
      case "down":
        return <TrendingDown className="w-4 h-4 text-red-400" />;
      case "stable":
        return <Minus className="w-4 h-4 text-gray-400" />;
      default:
        return null;
    }
  };

  const getHealthSeverity = (health) => {
    if (health >= 98) return { color: "text-green-400", level: "Optimal" };
    if (health >= 95) return { color: "text-yellow-400", level: "Good" };
    if (health >= 90) return { color: "text-orange-400", level: "Warning" };
    return { color: "text-red-400", level: "Critical" };
  };

  const handleAlertClick = (alert) => {
    onAlertClick?.(alert?.vesselId ?? alert?.mmsi);
  };

  const handleAcknowledge = (a, e) => {
    e.stopPropagation();
    setAckMap((prev) => ({ ...prev, [alertKey(a)]: true }));
    // Fire-and-forget: write to tamper-evident audit log
    logAlertAction({
      action:    "ALERT_ACK",
      alertId:   alertKey(a),
      vesselId:  a.mmsi ?? a.vesselId ?? null,
      timestamp: a.timestamp,
      details:   `Alert acknowledged: ${a._typeNorm ?? a.type ?? "unknown"} on ${a.vessel || (a.mmsi ? `MMSI-${a.mmsi}` : "Unknown Vessel")}`,
    });
  };

  const handleDismiss = (a, e) => {
    e.stopPropagation();
    setDismissMap((prev) => ({ ...prev, [alertKey(a)]: true }));
    // Fire-and-forget: write to tamper-evident audit log
    logAlertAction({
      action:    "ALERT_DISMISSED",
      alertId:   alertKey(a),
      vesselId:  a.mmsi ?? a.vesselId ?? null,
      timestamp: a.timestamp,
      details:   `Alert dismissed: ${a._typeNorm ?? a.type ?? "unknown"} on ${a.vessel || (a.mmsi ? `MMSI-${a.mmsi}` : "Unknown Vessel")}`,
    });
  };

  // ✅ Triaging + Deduping + Filtering + SEARCH
  const triagedAlerts = useMemo(() => {
    const sevWeight = { high: 3, medium: 2, low: 1 };

    const normalized = (propAlerts || []).map((a, idx) => {
      const ts =
        a.timestamp instanceof Date ? a.timestamp : new Date(a.timestamp || Date.now());
      const sev = String(a.severity || "low").toLowerCase();
      const t = normType(a.type);

      return {
        ...a,
        _typeNorm: t,
        mmsi: a.mmsi ?? a.vesselId,
        vessel: a.vessel ?? (a.mmsi ? `MMSI-${a.mmsi}` : `Vessel-${idx + 1}`),
        severity: sev,
        timestamp: ts,
      };
    });

    // ✅ Deduplicate latest per (type + mmsi)
    const latestMap = new Map();
    for (const a of normalized) {
      const key = `${a._typeNorm}|${a.mmsi}`;
      const existing = latestMap.get(key);
      if (!existing || a.timestamp.getTime() > existing.timestamp.getTime()) {
        latestMap.set(key, a);
      }
    }

    let visible = Array.from(latestMap.values());

    // Remove ack/dismissed
    visible = visible.filter((a) => !ackMap[alertKey(a)] && !dismissMap[alertKey(a)]);

    // Type filter
    if (typeFilter !== "all") {
      visible = visible.filter((a) => a._typeNorm === typeFilter);
    }

    // Severity filter (high/medium only)
    visible = visible.filter((a) => {
      const s = String(a.severity || "").toLowerCase();
      if (s === "high") return !!sevFilter.high;
      if (s === "medium") return !!sevFilter.medium;
      return false;
    });

    // ✅ Search filter (MMSI or vessel name)
    const q = searchQuery.trim().toLowerCase();
    if (q) {
      visible = visible.filter((a) => {
        const m = String(a.mmsi ?? a.vesselId ?? "").toLowerCase();
        const name = String(a.vessel ?? "").toLowerCase();
        return m.includes(q) || name.includes(q);
      });
    }

    // Sort by severity then recency
    visible.sort((a, b) => {
      const sa = sevWeight[a.severity] || 0;
      const sb = sevWeight[b.severity] || 0;
      if (sb !== sa) return sb - sa;
      return b.timestamp.getTime() - a.timestamp.getTime();
    });

    return visible;
  }, [propAlerts, ackMap, dismissMap, typeFilter, sevFilter, searchQuery]);

  const healthInfo = getHealthSeverity(stats.systemHealth);

  if (!datasetUploaded) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400 text-sm border-l border-cyan-500/20 bg-slate-900/40">
        <div className="text-cyan-400 text-lg mb-2">📡 Awaiting Dataset Upload</div>
        <p className="text-gray-400 text-center max-w-[220px] leading-relaxed">
          Import your AIS dataset to activate <br />
          <span className="text-cyan-300">Live Alerts</span>,{" "}
          <span className="text-cyan-300">System Status</span>, <br />
          and <span className="text-cyan-300">Anomaly Breakdown</span>.
        </p>
        <div className="w-3 h-3 bg-cyan-400 rounded-full animate-pulse mt-4"></div>
      </div>
    );
  }

  return (
    <div className="w-full bg-slate-900/50 border-l border-cyan-500/20 flex flex-col">
      <div className="p-6 space-y-6 overflow-y-auto">
        {/* === Live Alerts === */}
        <div className="bg-slate-800/30 rounded-xl border border-cyan-500/30 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold text-cyan-400">Live Alerts</h3>
            <span className="text-xs text-gray-400">
              Showing {Math.min(5, triagedAlerts.length)} / {triagedAlerts.length}
            </span>
          </div>

          {/* Active filter indicator */}
          <div className="text-xs text-gray-400 mb-3">
            Filters:
            <span className="ml-1 capitalize text-cyan-300">{typeFilter}</span>
            {" · "}
            {sevFilter.high && <span className="text-red-300 ml-1">High</span>}
            {sevFilter.medium && <span className="text-yellow-300 ml-1">Medium</span>}
            {searchQuery.trim() && (
              <span className="ml-2 text-cyan-300">· Search: "{searchQuery.trim()}"</span>
            )}
          </div>

          {/* Filters row */}
          <div className="mb-4 space-y-2">
            {/* Type filter */}
            <div className="flex gap-2">
              {[
                { key: "all", label: "All" },
                { key: "spoofing", label: "Spoofing" },
                { key: "loitering", label: "Loitering" },
              ].map((t) => (
                <button
                  key={t.key}
                  onClick={() => setTypeFilter(t.key)}
                  className={`px-3 py-1 rounded-lg text-xs border transition-all ${
                    typeFilter === t.key
                      ? "bg-cyan-600/30 text-cyan-300 border-cyan-500/50"
                      : "bg-slate-700/30 text-gray-300 border-slate-600/40 hover:bg-slate-700/50"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {/* Severity filter (High / Medium only) */}
            <div className="flex gap-2">
              <button
                onClick={() => setSevFilter((p) => ({ ...p, high: !p.high }))}
                className={`px-3 py-1 rounded-lg text-xs border transition-all ${
                  sevFilter.high
                    ? "bg-red-600/25 text-red-200 border-red-500/50"
                    : "bg-slate-700/30 text-gray-400 border-slate-600/40"
                }`}
              >
                High
              </button>

              <button
                onClick={() => setSevFilter((p) => ({ ...p, medium: !p.medium }))}
                className={`px-3 py-1 rounded-lg text-xs border transition-all ${
                  sevFilter.medium
                    ? "bg-yellow-400/20 text-yellow-200 border-yellow-400/50"
                    : "bg-slate-700/30 text-gray-400 border-slate-600/40"
                }`}
              >
                Medium
              </button>
            </div>

            {/* ✅ Search bar */}
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search MMSI…"
              className="w-full bg-slate-700/30 text-gray-200 px-3 py-2 rounded-lg border border-slate-600/40 focus:outline-none focus:border-cyan-500/60 text-sm"
            />
          </div>

          {/* Alerts list */}
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {triagedAlerts.slice(0, 5).map((alert) => {
              const sev = String(alert.severity || "low").toLowerCase();
              const title = alert.vessel || (alert.mmsi ? `MMSI-${alert.mmsi}` : "Unknown Vessel");

              const desc =
                alert.description ||
                (alert._typeNorm === "loitering"
                  ? `Loitering detected (cluster: ${alert.cluster_size ?? "?"})`
                  : alert._typeNorm === "spoofing"
                  ? `GPS inconsistency (score: ${
                      typeof alert.score === "number" ? alert.score.toFixed(3) : "N/A"
                    })`
                  : "Anomaly detected");

              return (
                <div
                  key={alertKey(alert)}
                  className="p-3 rounded-lg border border-cyan-500/20 bg-slate-700/30 hover:bg-slate-700/50 cursor-pointer"
                  onClick={() => handleAlertClick(alert)}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="font-semibold text-sm text-white">{title}</div>
                      <div className="text-xs text-gray-300 capitalize">{alert._typeNorm} Alert</div>
                    </div>

                    <div className="text-xs text-gray-400 whitespace-nowrap ml-2">
                      {alert.timestamp instanceof Date && Number.isFinite(alert.timestamp.getTime())
                        ? alert.timestamp.toLocaleTimeString()
                        : ""}
                    </div>
                  </div>

                  <div className="text-xs text-gray-300 mb-3">{desc}</div>

                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => handleAcknowledge(alert, e)}
                        className="px-2 py-1 bg-cyan-600 hover:bg-cyan-700 text-white rounded text-xs"
                      >
                        ✓ ACK
                      </button>

                      <button
                        onClick={(e) => handleDismiss(alert, e)}
                        className="px-2 py-1 bg-gray-700 hover:bg-gray-600 text-red-400 rounded text-xs"
                      >
                        ✕ Dismiss
                      </button>
                    </div>

                    <span
                      className={`px-2 py-1 text-xs font-bold rounded ${
                        sev === "high"
                          ? "bg-red-600 text-white"
                          : sev === "medium"
                          ? "bg-yellow-400 text-black"
                          : "bg-green-500 text-white"
                      }`}
                    >
                      {sev.toUpperCase()}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          <button className="w-full mt-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg text-sm">
            View All Alerts ({triagedAlerts.length})
          </button>
        </div>

        {/* === System Status === */}
        <div className="bg-slate-800/30 rounded-xl border border-cyan-500/30 p-4">
          <h3 className="text-lg font-semibold text-cyan-400 mb-4">System Status</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-gray-300">Vessels Tracked</span>
              <div className="flex items-center space-x-2">
                <span className="text-xl font-mono text-cyan-400">
                  {(stats.vesselsTracked ?? 0).toLocaleString()}
                </span>
                {getTrendIcon(stats.trends?.vessels)}
              </div>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-gray-300">Total Anomalies</span>
              <div className="flex items-center space-x-2">
                <span className="text-xl font-mono text-orange-400">{stats.anomaliesDetected ?? 0}</span>
                {getTrendIcon(stats.trends?.anomalies)}
              </div>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-gray-300">System Health</span>
              <div className="flex items-center space-x-2">
                <span className={`text-xl font-mono ${healthInfo.color}`}>
                  {(stats.systemHealth ?? 0).toFixed(1)}%
                </span>
                <div className="w-16 h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-green-500 to-cyan-500 transition-all duration-1000"
                    style={{ width: `${stats.systemHealth ?? 0}%` }}
                  />
                </div>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-600/30 text-xs text-gray-400">
              Status: <span className={healthInfo.color}>{healthInfo.level}</span> | Last Update:{" "}
              {stats.lastUpdate ? new Date(stats.lastUpdate).toLocaleTimeString() : ""}
            </div>
          </div>
        </div>

        {/* === Anomaly Breakdown === */}
        <div className="bg-slate-800/30 backdrop-blur-sm rounded-xl border border-cyan-500/30 p-4">
          <h3 className="text-lg font-semibold text-cyan-400 mb-4">Anomaly Breakdown</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="text-center p-3 rounded-lg bg-gradient-to-br from-red-500 to-red-700 border border-red-400/50">
              <div className="text-red-200 text-xl font-bold">{stats.anomalyBreakdown?.spoofing ?? 0}</div>
              <div className="text-xs text-gray-300">Spoofing</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-gradient-to-br from-amber-400 to-orange-600 border border-orange-400/50">
              <div className="text-yellow-100 text-xl font-bold">{stats.anomalyBreakdown?.loitering ?? 0}</div>
              <div className="text-xs text-gray-300">Loitering</div>
            </div>

            
          </div>
        </div>
      </div>
    </div>
  );
};

export default RightPanel;
