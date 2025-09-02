import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Minus } from "lucide-react";  // ✅ Correct import

const RightPanel = ({ onAlertClick }) => {
  const [collapsed, setCollapsed] = useState(false);

  const [stats, setStats] = useState({
    vesselsTracked: 1247,
    anomaliesDetected: 23,
    systemHealth: 98.7,
    lastUpdate: new Date(),
    trends: {
      vessels: 'up',
      anomalies: 'down'
    },
    anomalyBreakdown: {
      spoofing: 8,
      loitering: 9,
      speed: 4,
      deviation: 2
    }
  });

  const [alerts, setAlerts] = useState([
    { id: 1, type: 'spoofing', vessel: 'MV-ATLANTIC-STAR', vesselId: 5, timestamp: new Date(Date.now() - 300000), severity: 'high', acknowledged: false, description: 'GPS signal inconsistency detected' },
    { id: 2, type: 'loitering', vessel: 'GULF-RUNNER-07', vesselId: 8, timestamp: new Date(Date.now() - 600000), severity: 'medium', acknowledged: false, description: 'Vessel stationary for 45 minutes' },
    { id: 3, type: 'speed', vessel: 'OCEAN-BREEZE-12', vesselId: 12, timestamp: new Date(Date.now() - 900000), severity: 'low', acknowledged: false, description: 'Excessive speed in restricted zone' },
    { id: 4, type: 'deviation', vessel: 'SEA-HAWK-03', vesselId: 3, timestamp: new Date(Date.now() - 1200000), severity: 'medium', acknowledged: false, description: 'Route deviation from filed plan' },
    { id: 5, type: 'spoofing', vessel: 'TIDE-MASTER-21', vesselId: 14, timestamp: new Date(Date.now() - 1500000), severity: 'high', acknowledged: false, description: 'AIS transponder anomaly detected' },
  ]);

  // Periodic stats update
  useEffect(() => {
    const interval = setInterval(() => {
      setStats(prev => {
        const vesselChange = Math.floor(Math.random() * 3 - 1);
        const anomalyChange = Math.floor(Math.random() * 2 - 0.5);

        return {
          ...prev,
          vesselsTracked: Math.max(1200, prev.vesselsTracked + vesselChange),
          anomaliesDetected: Math.max(0, prev.anomaliesDetected + anomalyChange),
          systemHealth: Math.min(100, Math.max(95, prev.systemHealth + (Math.random() * 0.4 - 0.2))),
          lastUpdate: new Date(),
          trends: {
            vessels: vesselChange > 0 ? 'up' : vesselChange < 0 ? 'down' : 'stable',
            anomalies: anomalyChange > 0 ? 'up' : anomalyChange < 0 ? 'down' : 'stable'
          }
        };
      });
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  // === helpers ===
  const getTrendIcon = (trend) => {
    switch (trend) {
      case 'up':
        return <TrendingUp className="w-4 h-4 text-green-400" />;
      case 'down':
        return <TrendingDown className="w-4 h-4 text-red-400" />;
      case 'stable':
        return <Minus className="w-4 h-4 text-gray-400" />;
      default:
        return null;
    }
  };

  const getHealthSeverity = (health) => {
    if (health >= 98) return { color: 'text-green-400', level: 'Optimal' };
    if (health >= 95) return { color: 'text-yellow-400', level: 'Good' };
    if (health >= 90) return { color: 'text-orange-400', level: 'Warning' };
    return { color: 'text-red-400', level: 'Critical' };
  };

  const handleAlertClick = (alert) => {
    onAlertClick?.(alert.vesselId);
  };

  const handleAcknowledge = (alertId, e) => {
    e.stopPropagation();
    setAlerts(prev => prev.map(alert =>
      alert.id === alertId ? { ...alert, acknowledged: true } : alert
    ));
  };

  const handleDismiss = (alertId, e) => {
    e.stopPropagation();
    setAlerts(prev => prev.filter(alert => alert.id !== alertId));
  };

  const healthInfo = getHealthSeverity(stats.systemHealth);

  // === UI ===
  return (
    <div className={`transition-all duration-500 ease-in-out ${collapsed ? "w-10" : "w-80"} bg-slate-900/50 border-l border-cyan-500/20 flex flex-col relative`}>
      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -left-6 top-4 bg-slate-800/60 hover:bg-slate-700/80 
                   border border-cyan-500/30 text-cyan-400 px-2 py-1 rounded-r-lg text-xs"
      >
        {collapsed ? "›" : "‹"}
      </button>

      {!collapsed && (
        <div className="p-6 space-y-6 overflow-y-auto">
          {/* === System Status === */}
          <div className="bg-slate-800/30 rounded-xl border border-cyan-500/30 p-4">
            <h3 className="text-lg font-semibold text-cyan-400 mb-4">System Status</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-gray-300">Vessels Tracked</span>
                <div className="flex items-center space-x-2">
                  <span className="text-xl font-mono text-cyan-400">{stats.vesselsTracked.toLocaleString()}</span>
                  {getTrendIcon(stats.trends.vessels)}
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-300">Total Anomalies</span>
                <div className="flex items-center space-x-2">
                  <span className="text-xl font-mono text-orange-400">{stats.anomaliesDetected}</span>
                  {getTrendIcon(stats.trends.anomalies)}
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-300">System Health</span>
                <div className="flex items-center space-x-2">
                  <span className={`text-xl font-mono ${healthInfo.color}`}>{stats.systemHealth.toFixed(1)}%</span>
                  <div className="w-16 h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-green-500 to-cyan-500 transition-all duration-1000" style={{ width: `${stats.systemHealth}%` }}></div>
                  </div>
                </div>
              </div>
              <div className="pt-2 border-t border-slate-600/30 text-xs text-gray-400">
                Status: <span className={healthInfo.color}>{healthInfo.level}</span> | Last Update: {stats.lastUpdate.toLocaleTimeString()}
              </div>
            </div>
          </div>

          {/* === Anomaly Breakdown === */}
          <div className="bg-slate-800/30 backdrop-blur-sm rounded-xl border border-cyan-500/30 p-4">
            <h3 className="text-lg font-semibold text-cyan-400 mb-4">Anomaly Breakdown</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center p-3 rounded-lg bg-gradient-to-br from-red-500 to-red-700 border border-red-400/50">
                <div className="text-red-200 text-xl font-bold">{stats.anomalyBreakdown.spoofing}</div>
                <div className="text-xs text-gray-300">Spoofing</div>
              </div>
              <div className="text-center p-3 rounded-lg bg-gradient-to-br from-amber-400 to-orange-600 border border-orange-400/50">
                <div className="text-yellow-100 text-xl font-bold">{stats.anomalyBreakdown.loitering}</div>
                <div className="text-xs text-gray-300">Loitering</div>
              </div>
              <div className="text-center p-3 rounded-lg bg-gradient-to-br from-cyan-400 to-teal-500 border border-cyan-400/50">
                <div className="text-cyan-100 text-xl font-bold">{stats.anomalyBreakdown.speed}</div>
                <div className="text-xs text-gray-300">Speed</div>
              </div>
              <div className="text-center p-3 rounded-lg bg-gradient-to-br from-indigo-400 to-blue-600 border border-blue-400/50">
                <div className="text-blue-100 text-xl font-bold">{stats.anomalyBreakdown.deviation}</div>
                <div className="text-xs text-gray-300">Deviation</div>
              </div>
            </div>
          </div>

          {/* === Live Alerts === */}
          <div className="bg-slate-800/30 rounded-xl border border-cyan-500/30 p-4 flex-1">
            <h3 className="text-lg font-semibold text-cyan-400 mb-4">Live Alerts</h3>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {alerts.map((alert) => (
                <div
                  key={alert.id}
                  className={`p-3 rounded-lg border transition-all hover:scale-[1.02] ${alert.acknowledged ? 'opacity-60' : ''}`}
                  onClick={() => handleAlertClick(alert)}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="font-semibold text-sm text-white">{alert.vessel}</div>
                      <div className="text-xs text-gray-300 capitalize">{alert.type} Alert</div>
                    </div>
                    <div className="text-xs text-gray-400">{alert.timestamp.toLocaleTimeString()}</div>
                  </div>
                  <div className="text-xs text-gray-300 mb-2">{alert.description}</div>
                  <div className="flex items-center space-x-2">
                    {!alert.acknowledged && (
                      <button onClick={(e) => handleAcknowledge(alert.id, e)} className="px-2 py-1 bg-cyan-600 hover:bg-cyan-700 text-white rounded text-xs">✓ ACK</button>
                    )}
                    <button onClick={(e) => handleDismiss(alert.id, e)} className="px-2 py-1 bg-gray-700 hover:bg-gray-600 text-red-400 rounded text-xs">✕ Dismiss</button>
                    <span className={`px-2 py-1 text-xs font-bold rounded ${
                      alert.severity === 'high'
                        ? 'bg-red-600 text-white'
                        : alert.severity === 'medium'
                        ? 'bg-yellow-400 text-black'
                        : 'bg-green-500 text-white'
                    }`}>
                      {alert.severity.toUpperCase()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <button className="w-full mt-4 py-2 px-4 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg transition-all text-sm">
              View All Alerts ({alerts.length})
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default RightPanel;
