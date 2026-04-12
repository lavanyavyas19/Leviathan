// src/components/BottomChart.jsx
//
// CRASH FIX:
//   Previously accepted `alerts` prop (up to 200 full records) and bucketed
//   them in the browser.  Now accepts `chartData` prop — a pre-aggregated
//   hourly time series produced by GET /api/jobs/{id}/chart-data (≤ 48 items).
//   The browser never sees raw alert records for chart rendering.
//
// PROP CHANGES:
//   alerts    → REMOVED (was raw records, now handled server-side)
//   chartData → NEW     (pre-aggregated: [{time, spoofing, loitering, other, total}])

import React, { useState, useEffect, useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  ReferenceLine
} from 'recharts';

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────────────

/** Safely convert any timestamp value to a JS Date. */
const toDate = (v) => {
  if (v instanceof Date) return v;
  const d = new Date(v);
  return Number.isFinite(d.getTime()) ? d : null;
};

/**
 * Bucket a list of alert objects by time.
 * Returns an array of chart-data points sorted oldest → newest.
 *
 * @param {Array}  alerts  — transformed alert objects with a `timestamp` field
 * @param {number} buckets — how many time slices to create
 * @param {number} minT    — start of range (ms epoch)
 * @param {number} maxT    — end of range (ms epoch)
 * @param {boolean} hourly — true → label HH:MM, false → label MM/DD
 */
function bucketAlerts(alerts, buckets, minT, maxT, hourly) {
  const range  = maxT - minT || 3_600_000; // floor at 1 h
  const stepMs = range / buckets;
  const data   = [];

  for (let i = 0; i < buckets; i++) {
    const bucketStart = minT + i * stepMs;
    const bucketEnd   = minT + (i + 1) * stepMs;
    const bucketMid   = (bucketStart + bucketEnd) / 2;

    const inBucket = alerts.filter((a) => {
      const ts = toDate(a.timestamp)?.getTime();
      return ts != null && ts >= bucketStart && ts < bucketEnd;
    });

    const spoofing  = inBucket.filter((a) => a.type === 'spoofing').length;
    const loitering = inBucket.filter((a) => a.type === 'loitering').length;
    const other     = inBucket.filter(
      (a) => a.type !== 'spoofing' && a.type !== 'loitering'
    ).length;

    const d = new Date(bucketMid);
    const timeLabel = hourly
      ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      : d.toLocaleDateString([], { month: '2-digit', day: '2-digit' });

    data.push({
      time:     timeLabel,
      fullTime: d.toLocaleString(),
      total:    spoofing + loitering + other,
      spoofing,
      loitering,
      other,
      timestamp: bucketMid,
    });
  }

  return data;
}


// ─────────────────────────────────────────────────────────────────────────────
// COMPONENT
// ─────────────────────────────────────────────────────────────────────────────

const BottomChart = ({
  jobId,                  // kept for prop-passing / future direct-fetch
  chartData: propChartData,  // pre-aggregated series from GET /chart-data (≤ 48 items)
  onChartClick,
  onAnomalyFilter,
  onVesselHighlight,
}) => {
  const [timeFilter,    setTimeFilter]    = useState('24h');
  const [normalized,    setNormalized]    = useState(false);
  const [showBaseline,  setShowBaseline]  = useState(true);

  // ── Determine data source ─────────────────────────────────────────────────
  // Pre-aggregated backend data takes priority.
  // Format it to match the chart's data contract: add a display `time` label.
  const backendChartData = useMemo(() => {
    if (!Array.isArray(propChartData) || propChartData.length === 0) return [];

    return propChartData.map((bucket) => {
      // bucket.time is ISO string like "2024-01-15T14:00:00"
      let label = bucket.time;
      try {
        const d = new Date(bucket.time);
        if (Number.isFinite(d.getTime())) {
          label = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        }
      } catch {/* keep raw label */}

      return {
        time:      label,
        fullTime:  bucket.time,
        total:     Number(bucket.total   || 0),
        spoofing:  Number(bucket.spoofing  || 0),
        loitering: Number(bucket.loitering || 0),
        other:     Number(bucket.other   || 0),
        timestamp: (() => { try { return new Date(bucket.time).getTime(); } catch { return 0; } })(),
      };
    });
  }, [propChartData]);

  const hasRealData = backendChartData.length > 0;

  // ── Mock-data chart series (only when no dataset uploaded) ────────────────
  const [mockChartData, setMockChartData] = useState([]);

  useEffect(() => {
    if (hasRealData) return; // don't generate mock when real data exists

    const now = new Date();
    let intervals, stepSize;
    switch (timeFilter) {
      case '7d':  intervals = 7;  stepSize = 86_400_000;  break;
      case '30d': intervals = 30; stepSize = 86_400_000;  break;
      default:    intervals = 24; stepSize = 3_600_000;
    }

    const dataPoints = [];
    for (let i = intervals - 1; i >= 0; i--) {
      const time     = new Date(now.getTime() - i * stepSize);
      const spoofing = Math.floor(Math.random() * 8)  + 1;
      const loitering= Math.floor(Math.random() * 12) + 3;
      const other    = Math.floor(Math.random() * 15) + 5;

      dataPoints.push({
        time: time.toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit',
          ...(timeFilter !== '24h' && { month: '2-digit', day: '2-digit' }),
        }),
        fullTime:  time.toLocaleString(),
        total:     spoofing + loitering + other,
        spoofing,
        loitering,
        other,
        timestamp: time.getTime(),
      });
    }

    setMockChartData(dataPoints);
  }, [timeFilter, hasRealData]);

  // ── Active chart data ─────────────────────────────────────────────────────
  const chartData = hasRealData ? backendChartData : mockChartData;

  // ── Summary + derived values ──────────────────────────────────────────────
  const summaryTotals = useMemo(() => {
    if (!Array.isArray(chartData) || chartData.length === 0)
      return { spoofing: 0, loitering: 0, total: 0 };
    return {
      spoofing:  chartData.reduce((s, d) => s + (d.spoofing  || 0), 0),
      loitering: chartData.reduce((s, d) => s + (d.loitering || 0), 0),
      total:     chartData.reduce((s, d) => s + (d.total     || 0), 0),
    };
  }, [chartData]);

  const peakValues = useMemo(() => {
    if (!Array.isArray(chartData) || chartData.length === 0)
      return { spoofing: null, loitering: null };

    let maxS = { value: -1, index: -1 };
    let maxL = { value: -1, index: -1 };

    chartData.forEach((d, i) => {
      if (d.spoofing  > maxS.value) maxS = { value: d.spoofing,  index: i };
      if (d.loitering > maxL.value) maxL = { value: d.loitering, index: i };
    });

    return {
      spoofing:  maxS.index >= 0 ? { ...chartData[maxS.index], index: maxS.index } : null,
      loitering: maxL.index >= 0 ? { ...chartData[maxL.index], index: maxL.index } : null,
    };
  }, [chartData]);

  // Mock vessel count for normalisation denominator
  const vesselCount = 1247;

  const baselineValue = useMemo(() => {
    if (!Array.isArray(chartData) || chartData.length === 0) return 0;
    const sum = chartData.reduce((a, d) => a + (d.total || 0), 0);
    return Math.round(sum / chartData.length);
  }, [chartData]);

  const spikeAnnotations = useMemo(() => {
    if (!Array.isArray(chartData) || chartData.length === 0) return [];
    const threshold = baselineValue * 1.5;
    return chartData
      .map((d, index) => {
        if (d.total <= threshold) return null;
        let annotation = '';
        if (d.spoofing  > d.loitering && d.spoofing  > 5) annotation = 'Spoofing surge';
        else if (d.loitering > d.spoofing && d.loitering > 8) annotation = 'Loitering cluster';
        else if (d.total > baselineValue * 2)                  annotation = 'Anomaly spike';
        return annotation ? { index, annotation, value: d.total, time: d.time } : null;
      })
      .filter(Boolean);
  }, [chartData, baselineValue]);

  const insightsSummary = useMemo(() => {
    if (!Array.isArray(chartData) || chartData.length === 0) return '';

    const maxTotal = Math.max(...chartData.map((d) => d.total));
    const insights = [];

    if (maxTotal > baselineValue * 1.5)
      insights.push(`Peak anomaly activity ${Math.round((maxTotal / baselineValue - 1) * 100)}% above baseline`);

    if (summaryTotals.spoofing > summaryTotals.loitering)
      insights.push(`Spoofing incidents dominate (${summaryTotals.spoofing} vs ${summaryTotals.loitering} loitering)`);
    else if (summaryTotals.loitering > summaryTotals.spoofing * 1.2)
      insights.push(`Loitering activity elevated (${summaryTotals.loitering} incidents detected)`);

    if (spikeAnnotations.length > 0)
      insights.push(`${spikeAnnotations.length} significant spike${spikeAnnotations.length > 1 ? 's' : ''} detected`);

    const trend =
      chartData.length > 1
        ? chartData[chartData.length - 1].total > chartData[0].total
          ? 'increasing'
          : 'decreasing'
        : 'stable';
    insights.push(`Overall trend: ${trend}`);

    return insights.join('. ') + '.';
  }, [chartData, baselineValue, summaryTotals, spikeAnnotations]);

  // ── Normalized display data ───────────────────────────────────────────────
  const displayData = useMemo(() => {
    if (!normalized || !Array.isArray(chartData)) return chartData;
    return chartData.map((d) => ({
      ...d,
      spoofing:  vesselCount > 0 ? Number(((d.spoofing  / vesselCount) * 100).toFixed(2)) : d.spoofing,
      loitering: vesselCount > 0 ? Number(((d.loitering / vesselCount) * 100).toFixed(2)) : d.loitering,
      total:     vesselCount > 0 ? Number(((d.total     / vesselCount) * 100).toFixed(2)) : d.total,
      other:     vesselCount > 0 ? Number(((d.other     / vesselCount) * 100).toFixed(2)) : d.other,
    }));
  }, [chartData, normalized, vesselCount]);

  const aggregationSubtitle = hasRealData
    ? `${backendChartData.reduce((s, d) => s + d.total, 0)} detected events — real data (hourly aggregation)`
    : timeFilter === '24h'
    ? 'Hourly aggregation (sample data — upload a dataset)'
    : 'Daily aggregation (sample data — upload a dataset)';

  // ── Tooltip ───────────────────────────────────────────────────────────────
  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    const data     = payload[0]?.payload;
    const fullTime = data?.fullTime || label;

    return (
      <div className="bg-slate-800/95 backdrop-blur-sm p-3 rounded-lg border border-cyan-500/30 shadow-xl min-w-[200px]">
        <p className="text-cyan-400 font-semibold mb-2 text-sm">{fullTime}</p>
        <div className="space-y-1">
          {payload.map((entry) => (
            <div key={entry.dataKey} className="flex justify-between items-center">
              <span className="text-gray-400 text-xs" style={{ color: entry.color }}>{entry.name}:</span>
              <span className="font-semibold text-sm ml-2" style={{ color: entry.color }}>{entry.value}</span>
            </div>
          ))}
        </div>
        {data && (
          <div className="mt-2 pt-2 border-t border-slate-600">
            <p className="text-xs text-gray-500 italic">
              {data.spoofing > data.loitering
                ? 'Spoofing dominant'
                : data.loitering > 0
                ? 'Loitering dominant'
                : 'Normal operations'}
            </p>
          </div>
        )}
      </div>
    );
  };

  // ── Click handler ─────────────────────────────────────────────────────────
  const handleChartClick = (data) => {
    if (!data?.activePayload?.[0]) return;
    const clickedData    = data.activePayload[0].payload;
    const clickedDataKey = data.activePayload[0].dataKey;

    let anomalyType = null;
    if (clickedDataKey === 'spoofing')  anomalyType = 'spoofing';
    else if (clickedDataKey === 'loitering') anomalyType = 'loitering';

    if (anomalyType && onAnomalyFilter)
      onAnomalyFilter({ type: anomalyType, timestamp: clickedData.timestamp, time: clickedData.time });

    if (onVesselHighlight && clickedData)
      onVesselHighlight({ timestamp: clickedData.timestamp, anomalyType });

    if (onChartClick) onChartClick(clickedData);
  };

  // ── Peak dot renderer ─────────────────────────────────────────────────────
  const PeakDot = ({ cx, cy, payload, dataKey, peakValue }) => {
    if (!peakValue || !payload || payload.timestamp == null) return null;
    if (payload.timestamp !== peakValue.timestamp)           return null;
    return (
      <g>
        <circle cx={cx} cy={cy} r={6}
          fill={dataKey === 'spoofing' ? '#ff4444' : '#ff8c00'}
          stroke="white" strokeWidth={2}
        />
        <circle cx={cx} cy={cy} r={8}
          fill={dataKey === 'spoofing' ? '#ff4444' : '#ff8c00'}
          opacity={0.3} className="animate-ping"
        />
      </g>
    );
  };

  const renderPeakDotSpoofing  = (props) => { const { key, ...rest } = props; return <PeakDot key={key} {...rest} peakValue={peakValues.spoofing}  dataKey="spoofing"  />; };
  const renderPeakDotLoitering = (props) => { const { key, ...rest } = props; return <PeakDot key={key} {...rest} peakValue={peakValues.loitering} dataKey="loitering" />; };

  // ── Empty state ───────────────────────────────────────────────────────────
  if (!hasRealData && mockChartData.length === 0) {
    return (
      <div className="bg-slate-800/30 backdrop-blur-sm border-t border-cyan-500/20 p-4 flex items-center justify-center h-64">
        <p className="text-gray-500 text-sm">Upload a dataset to see anomaly detection trends.</p>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="bg-slate-800/30 backdrop-blur-sm border-t border-cyan-500/20 p-4">

      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        <div>
          <h3 className="text-lg font-semibold text-cyan-400 flex items-center">
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
              />
            </svg>
            Anomaly Detection Trends
          </h3>
          <p className="text-xs text-gray-400 ml-7 mt-0.5">{aggregationSubtitle}</p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => setNormalized(!normalized)}
            className={`px-3 py-1 rounded-lg text-xs transition-all ${
              normalized
                ? 'bg-cyan-600/30 text-cyan-400 border border-cyan-500/50'
                : 'bg-slate-700/30 text-gray-400 hover:bg-slate-600/30 border border-slate-600/30'
            }`}
            title="Toggle normalized metrics (per 100 vessels)"
          >
            Normalized
          </button>

          <button
            onClick={() => setShowBaseline(!showBaseline)}
            className={`px-3 py-1 rounded-lg text-xs transition-all ${
              showBaseline
                ? 'bg-cyan-600/30 text-cyan-400 border border-cyan-500/50'
                : 'bg-slate-700/30 text-gray-400 hover:bg-slate-600/30 border border-slate-600/30'
            }`}
            title="Toggle baseline reference line"
          >
            Baseline
          </button>

          {/* Time-filter buttons — only meaningful for mock data */}
          {!hasRealData && ['24h', '7d', '30d'].map((f) => (
            <button
              key={f}
              onClick={() => setTimeFilter(f)}
              className={`px-3 py-1 rounded-lg text-sm transition-all ${
                timeFilter === f
                  ? 'bg-cyan-600/30 text-cyan-400 border border-cyan-500/50'
                  : 'bg-slate-700/30 text-gray-400 hover:bg-slate-600/30 border border-slate-600/30'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Summary row */}
      <div className="flex items-center justify-center space-x-4 mb-3 px-2">
        <div className="flex items-center space-x-2 px-3 py-1.5 bg-slate-800/50 rounded-lg border border-red-500/30">
          <div className="w-2 h-2 bg-red-500 rounded-full" />
          <span className="text-xs text-gray-400">Spoofing:</span>
          <span className="text-sm font-semibold text-red-400">
            {normalized ? `${((summaryTotals.spoofing / vesselCount) * 100).toFixed(2)}%` : summaryTotals.spoofing}
          </span>
        </div>
        <div className="flex items-center space-x-2 px-3 py-1.5 bg-slate-800/50 rounded-lg border border-orange-500/30">
          <div className="w-2 h-2 bg-orange-500 rounded-full" />
          <span className="text-xs text-gray-400">Loitering:</span>
          <span className="text-sm font-semibold text-orange-400">
            {normalized ? `${((summaryTotals.loitering / vesselCount) * 100).toFixed(2)}%` : summaryTotals.loitering}
          </span>
        </div>
        <div className="flex items-center space-x-2 px-3 py-1.5 bg-slate-800/50 rounded-lg border border-cyan-500/30">
          <div className="w-2 h-2 bg-cyan-500 rounded-full" />
          <span className="text-xs text-gray-400">Total:</span>
          <span className="text-sm font-semibold text-cyan-400">
            {normalized ? `${((summaryTotals.total / vesselCount) * 100).toFixed(2)}%` : summaryTotals.total}
          </span>
        </div>
      </div>

      {/* Insights */}
      <div className="mb-3 px-2 py-2 bg-slate-800/40 rounded-lg border border-cyan-500/20">
        <div className="flex items-start space-x-2">
          <svg className="w-4 h-4 text-cyan-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-xs text-gray-300 leading-relaxed">{insightsSummary}</p>
        </div>
      </div>

      {/* Chart */}
      <div className="h-44 relative">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={displayData}
            margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
            onClick={handleChartClick}
          >
            <XAxis
              dataKey="time"
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#94a3b8', fontSize: 12 }}
              interval="preserveStartEnd"
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#94a3b8', fontSize: 12 }}
              label={
                normalized
                  ? { value: 'Per 100 vessels', angle: -90, position: 'insideLeft', fill: '#94a3b8', fontSize: 10 }
                  : undefined
              }
            />
            <Tooltip content={<CustomTooltip />} />

            {showBaseline && (
              <ReferenceLine
                y={normalized ? Number(((baselineValue / vesselCount) * 100).toFixed(2)) : baselineValue}
                stroke="#64748b" strokeWidth={1.5} strokeDasharray="3 3" opacity={0.4}
                label={{ value: 'Expected baseline', position: 'right', fill: '#94a3b8', fontSize: 10, offset: 5 }}
              />
            )}

            <Line type="monotone" dataKey="spoofing"  stroke="#ff4444" strokeWidth={2}
              dot={renderPeakDotSpoofing}
              activeDot={{ r: 6, stroke: '#ff4444', strokeWidth: 2, cursor: 'pointer' }}
              name="Spoofing"  style={{ cursor: 'pointer' }}
            />
            <Line type="monotone" dataKey="loitering" stroke="#ff8c00" strokeWidth={2}
              dot={renderPeakDotLoitering}
              activeDot={{ r: 6, stroke: '#ff8c00', strokeWidth: 2, cursor: 'pointer' }}
              name="Loitering" style={{ cursor: 'pointer' }}
            />
            <Line type="monotone" dataKey="other"     stroke="#00d4ff" strokeWidth={2}
              dot={{ fill: '#00d4ff', strokeWidth: 0, r: 4 }}
              activeDot={{ r: 6, stroke: '#00d4ff', strokeWidth: 2, cursor: 'pointer' }}
              name="Other"     style={{ cursor: 'pointer' }}
            />
          </LineChart>
        </ResponsiveContainer>

        <div className="absolute top-2 right-2 text-xs text-gray-500">
          Click lines/points to filter vessels
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center space-x-6 mt-2">
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 bg-red-500 rounded-full" />
          <span className="text-xs text-gray-400">Spoofing</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 bg-orange-500 rounded-full" />
          <span className="text-xs text-gray-400">Loitering</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 bg-cyan-500 rounded-full" />
          <span className="text-xs text-gray-400">Other Anomalies</span>
        </div>
      </div>
    </div>
  );
};

export default BottomChart;
