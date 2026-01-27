import React, { useMemo, useState, useEffect } from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

/**
 * Build a stable key so ACK/Dismiss works even if list order changes.
 * Prefer timestamp when available.
 */
function alertKey(a) {
  const ts = a?.timestamp
    ? new Date(a.timestamp).toISOString()
    : "no-ts";
  return `${a?.type || "unknown"}|${a?.mmsi || a?.vesselId || "no-mmsi"}|${ts}`;
}

const RightPanel = ({
  onAlertClick,
  datasetUploaded,
  alerts: propAlerts = [],
  stats: propStats = null,
}) => {
  // Store ack/dismiss state keyed by stable alertKey
  const [ackMap, setAckMap] = useState({});
  const [dismissMap, setDismissMap] = useState({});

  // If a new dataset is uploaded and alerts reset, you can optionally clear states:
  useEffect(() => {
    // If you want: clear ack/dismiss whenever propAlerts changes completely.
    // Comment this out if you want ack state to persist.
    // setAckMap({});
    // setDismissMap({});
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
    const k = alertKey(a);
    setAckMap((prev) => ({ ...prev, [k]: true }));
  };

  const handleDismiss = (a, e) => {
    e.stopPropagation();
    const k = alertKey(a);
    setDismissMap((prev) => ({ ...prev, [k]: true }));
  };

  // ✅ Triaging logic: sort + dedupe per vessel/type
  const triagedAlerts = useMemo(() => {
    const sevWeight = { high: 3, medium: 2, low: 1 };

    // Normalize alert fields (defensive)
    const normalized = (propAlerts || []).map((a, idx) => {
      const ts = a.timestamp instanceof Date ? a.timestamp : new Date(a.timestamp || Date.now());
      return {
        ...a,
        // ensure these exist
        mmsi: a.mmsi ?? a.vesselId,
        vessel: a.vessel ?? (a.mmsi ? `MMSI-${a.mmsi}` : `Vessel-${idx + 1}`),
        severity: (a.severity || "low").toLowerCase(),
        timestamp: ts,
      };
    });

    // Deduplicate: keep latest per (type + mmsi)
    const latestMap = new Map();
    for (const a of normalized) {
      const key = `${a.type}|${a.mmsi}`;
      const existing = latestMap.get(key);
      if (!existing || a.timestamp.getTime() > existing.timestamp.getTime()) {
        latestMap.set(key, a);
      }
    }

    const deduped = Array.from(latestMap.values());

    // Remove ack/dismissed
    const visible = deduped.filter((a) => {
      const k = alertKey(a);
      return !ackMap[k] && !dismissMap[k];
    });

    // Sort by severity then recency
    visible.sort((a, b) => {
      const sa = sevWeight[a.severity] || 0;
      const sb = sevWeight[b.severity] || 0;
      if (sb !== sa) return sb - sa;
      return b.timestamp.getTime() - a.timestamp.getTime();
    });

    return visible;
  }, [propAlerts, ackMap, dismissMap]);

  const healthInfo = getHealthSeverity(stats.systemHealth);

  if (!datasetUploaded) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400 text-sm border-l border-cyan-500/20 bg-slate-900/40">
        <div className="text-cyan-400 text-lg mb-2">📡 Awaiting Dataset Upload</div>
        <p className="text-gray-400 text-center max-w-[220px] leading-relaxed">
          Import your AIS dataset to activate <br />
          <span className="text-cyan-300">Live Alerts</span>, <span className="text-cyan-300">System Status</span>, <br />
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
          <h3 className="text-lg font-semibold text-cyan-400 mb-4">Live Alerts</h3>

          <div className="space-y-3 max-h-96 overflow-y-auto">
            {triagedAlerts.slice(0, 5).map((alert) => {
              const sev = (alert.severity || "low").toLowerCase();
              return (
                <div
                  key={alertKey(alert)}
                  className="p-3 rounded-lg border border-cyan-500/20 bg-slate-700/30 hover:bg-slate-700/50 cursor-pointer"
                  onClick={() => handleAlertClick(alert)}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="font-semibold text-sm text-white">{alert.vessel}</div>
                      <div className="text-xs text-gray-300 capitalize">{alert.type} Alert</div>
                    </div>

                    <div className="text-xs text-gray-400 whitespace-nowrap ml-2">
                      {alert.timestamp.toLocaleTimeString()}
                    </div>
                  </div>

                  <div className="text-xs text-gray-300 mb-3">{alert.description}</div>

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
            <div className="text-center p-3 rounded-lg bg-gradient-to-br from-cyan-400 to-teal-500 border border-cyan-400/50">
              <div className="text-cyan-100 text-xl font-bold">{stats.anomalyBreakdown?.speed ?? 0}</div>
              <div className="text-xs text-gray-300">Speed</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-gradient-to-br from-indigo-400 to-blue-600 border border-blue-400/50">
              <div className="text-blue-100 text-xl font-bold">{stats.anomalyBreakdown?.deviation ?? 0}</div>
              <div className="text-xs text-gray-300">Deviation</div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

export default RightPanel;
