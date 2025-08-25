import React, { useState, useEffect } from 'react';

const RightPanel = ({ onAlertClick }) => {
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
    { 
      id: 1, 
      type: 'spoofing', 
      vessel: 'MV-ATLANTIC-STAR', 
      vesselId: 5,
      timestamp: new Date(Date.now() - 300000), 
      severity: 'high',
      acknowledged: false,
      description: 'GPS signal inconsistency detected'
    },
    { 
      id: 2, 
      type: 'loitering', 
      vessel: 'GULF-RUNNER-07', 
      vesselId: 8,
      timestamp: new Date(Date.now() - 600000), 
      severity: 'medium',
      acknowledged: false,
      description: 'Vessel stationary for 45 minutes'
    },
    { 
      id: 3, 
      type: 'speed', 
      vessel: 'OCEAN-BREEZE-12', 
      vesselId: 12,
      timestamp: new Date(Date.now() - 900000), 
      severity: 'low',
      acknowledged: true,
      description: 'Excessive speed in restricted zone'
    },
    { 
      id: 4, 
      type: 'deviation', 
      vessel: 'SEA-HAWK-03', 
      vesselId: 3,
      timestamp: new Date(Date.now() - 1200000), 
      severity: 'medium',
      acknowledged: false,
      description: 'Route deviation from filed plan'
    },
    { 
      id: 5, 
      type: 'spoofing', 
      vessel: 'TIDE-MASTER-21', 
      vesselId: 14,
      timestamp: new Date(Date.now() - 1500000), 
      severity: 'high',
      acknowledged: true,
      description: 'AIS transponder anomaly detected'
    },
  ]);

  // Update stats periodically
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

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'high': return 'text-red-400 bg-red-500/20 border-red-500/30';
      case 'medium': return 'text-orange-400 bg-orange-500/20 border-orange-500/30';
      case 'low': return 'text-yellow-400 bg-yellow-500/20 border-yellow-500/30';
      default: return 'text-gray-400 bg-gray-500/20 border-gray-500/30';
    }
  };

  const getAlertIcon = (type) => {
    switch (type) {
      case 'spoofing': return '⛔';
      case 'loitering': return '🌀';
      case 'speed': return '⚡';
      case 'deviation': return '↔️';
      default: return '⚠️';
    }
  };

  const getTrendIcon = (trend) => {
    switch (trend) {
      case 'up': return <span className="text-green-400 text-sm">↗️</span>;
      case 'down': return <span className="text-red-400 text-sm">↘️</span>;
      case 'stable': return <span className="text-gray-400 text-sm">→</span>;
      default: return null;
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

  return (
    <div className="w-80 p-6 space-y-6">
      {/* Enhanced System Stats */}
      <div className="bg-slate-800/30 backdrop-blur-sm rounded-xl border border-cyan-500/30 p-4">
        <h3 className="text-lg font-semibold text-cyan-400 mb-4 flex items-center">
          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          System Status
        </h3>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-gray-300">Vessels Tracked</span>
            <div className="flex items-center space-x-2">
              <span className="text-xl font-mono text-cyan-400">{stats.vesselsTracked.toLocaleString()}</span>
              {getTrendIcon(stats.trends.vessels)}
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-gray-300">Total Anomalies</span>
            <div className="flex items-center space-x-2">
              <span className="text-xl font-mono text-orange-400">{stats.anomaliesDetected}</span>
              {getTrendIcon(stats.trends.anomalies)}
              <div className="w-2 h-2 bg-orange-500 rounded-full animate-pulse"></div>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-gray-300">System Health</span>
            <div className="flex items-center space-x-2">
              <span className={`text-xl font-mono ${healthInfo.color}`}>{stats.systemHealth.toFixed(1)}%</span>
              <div className="w-16 h-2 bg-slate-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-green-500 to-cyan-500 transition-all duration-1000"
                  style={{ width: `${stats.systemHealth}%` }}
                ></div>
              </div>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-600/30">
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-400">Status: <span className={healthInfo.color}>{healthInfo.level}</span></span>
              <span className="text-gray-400">Last Update: {stats.lastUpdate.toLocaleTimeString()}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Anomaly Breakdown */}
      <div className="bg-slate-800/30 backdrop-blur-sm rounded-xl border border-cyan-500/30 p-4">
        <h3 className="text-lg font-semibold text-cyan-400 mb-4">Anomaly Breakdown</h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="text-center p-2 bg-red-500/10 border border-red-500/30 rounded-lg">
            <div className="text-red-400 text-xl font-mono">{stats.anomalyBreakdown.spoofing}</div>
            <div className="text-xs text-gray-400">⛔ Spoofing</div>
          </div>
          <div className="text-center p-2 bg-orange-500/10 border border-orange-500/30 rounded-lg">
            <div className="text-orange-400 text-xl font-mono">{stats.anomalyBreakdown.loitering}</div>
            <div className="text-xs text-gray-400">🌀 Loitering</div>
          </div>
          <div className="text-center p-2 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <div className="text-yellow-400 text-xl font-mono">{stats.anomalyBreakdown.speed}</div>
            <div className="text-xs text-gray-400">⚡ Speed</div>
          </div>
          <div className="text-center p-2 bg-blue-500/10 border border-blue-500/30 rounded-lg">
            <div className="text-blue-400 text-xl font-mono">{stats.anomalyBreakdown.deviation}</div>
            <div className="text-xs text-gray-400">↔️ Deviation</div>
          </div>
        </div>
      </div>

      {/* Live Alerts Feed */}
      <div className="bg-slate-800/30 backdrop-blur-sm rounded-xl border border-cyan-500/30 p-4 flex-1">
        <h3 className="text-lg font-semibold text-cyan-400 mb-4 flex items-center">
          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          Live Alerts
        </h3>

        <div className="space-y-3 max-h-96 overflow-y-auto">
          {alerts.map((alert) => (
            <div 
              key={alert.id} 
              className={`p-3 rounded-lg border cursor-pointer transition-all hover:scale-[1.02] ${getSeverityColor(alert.severity)} ${
                alert.acknowledged ? 'opacity-60' : ''
              }`}
              onClick={() => handleAlertClick(alert)}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <span className="text-lg">{getAlertIcon(alert.type)}</span>
                  <div>
                    <div className="font-semibold text-sm">{alert.vessel}</div>
                    <div className="text-xs opacity-80 capitalize">{alert.type} Alert</div>
                  </div>
                </div>
                <div className="text-xs opacity-70">
                  {alert.timestamp.toLocaleTimeString()}
                </div>
              </div>
              
              <div className="text-xs opacity-80 mb-2">
                {alert.description}
              </div>

              <div className="flex items-center space-x-2">
                {!alert.acknowledged && (
                  <button
                    onClick={(e) => handleAcknowledge(alert.id, e)}
                    className="px-2 py-1 bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-400 rounded text-xs transition-all border border-cyan-500/30"
                  >
                    ✓ ACK
                  </button>
                )}
                <button
                  onClick={(e) => handleDismiss(alert.id, e)}
                  className="px-2 py-1 bg-red-600/20 hover:bg-red-600/30 text-red-400 rounded text-xs transition-all border border-red-500/30"
                >
                  ✕ Dismiss
                </button>
                <span className={`px-2 py-1 text-xs rounded border ${getSeverityColor(alert.severity)}`}>
                  {alert.severity.toUpperCase()}
                </span>
              </div>
            </div>
          ))}
        </div>

        <button className="w-full mt-4 py-2 px-4 bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-400 rounded-lg transition-all duration-200 border border-cyan-500/30 text-sm">
          View All Alerts ({alerts.length})
        </button>
      </div>

      {/* Quick Actions */}
      <div className="bg-slate-800/30 backdrop-blur-sm rounded-xl border border-cyan-500/30 p-4">
        <h3 className="text-lg font-semibold text-cyan-400 mb-4">Quick Actions</h3>
        <div className="grid grid-cols-2 gap-2">
          <button className="py-2 px-3 bg-teal-600/20 hover:bg-teal-600/30 text-teal-400 rounded-lg transition-all text-xs border border-teal-500/30">
            📊 Export Log
          </button>
          <button className="py-2 px-3 bg-orange-600/20 hover:bg-orange-600/30 text-orange-400 rounded-lg transition-all text-xs border border-orange-500/30">
            🚨 Alert Mode
          </button>
          <button className="py-2 px-3 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 rounded-lg transition-all text-xs border border-blue-500/30">
            🔄 Refresh Data
          </button>
          <button className="py-2 px-3 bg-purple-600/20 hover:bg-purple-600/30 text-purple-400 rounded-lg transition-all text-xs border border-purple-500/30">
            🔍 Full Screen
          </button>
        </div>
      </div>
    </div>
  );
};

export default RightPanel;