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

const BottomChart = ({ onChartClick, onAnomalyFilter, onVesselHighlight }) => {
  const [timeFilter, setTimeFilter] = useState('24h');
  const [chartData, setChartData] = useState([]);
  const [normalized, setNormalized] = useState(false);
  const [showBaseline, setShowBaseline] = useState(true);

  // Generate mock data based on time filter
  useEffect(() => {
    const generateData = () => {
      const now = new Date();
      let dataPoints = [];
      let intervals, stepSize;

      switch (timeFilter) {
        case '24h':
          intervals = 24;
          stepSize = 60 * 60 * 1000; // 1 hour
          break;
        case '7d':
          intervals = 7;
          stepSize = 24 * 60 * 60 * 1000; // 1 day
          break;
        case '30d':
          intervals = 30;
          stepSize = 24 * 60 * 60 * 1000; // 1 day
          break;
        default:
          intervals = 24;
          stepSize = 60 * 60 * 1000;
      }

      for (let i = intervals - 1; i >= 0; i--) {
        const time = new Date(now.getTime() - i * stepSize);
        const baseAnomalies = Math.floor(Math.random() * 15) + 5;
        const spoofing = Math.floor(Math.random() * 8) + 1;
        const loitering = Math.floor(Math.random() * 12) + 3;

        dataPoints.push({
          time: time.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            ...(timeFilter !== '24h' && { month: '2-digit', day: '2-digit' })
          }),
          fullTime: time.toLocaleString(),
          total: baseAnomalies + spoofing + loitering,
          spoofing,
          loitering,
          other: baseAnomalies,
          timestamp: time.getTime()
        });
      }

      return dataPoints;
    };

    setChartData(generateData());
  }, [timeFilter]);

  // Calculate summary totals
  const summaryTotals = useMemo(() => {
    if (!Array.isArray(chartData) || chartData.length === 0) {
      return { spoofing: 0, loitering: 0, total: 0 };
    }
    return {
      spoofing: chartData.reduce((sum, d) => sum + (d.spoofing || 0), 0),
      loitering: chartData.reduce((sum, d) => sum + (d.loitering || 0), 0),
      total: chartData.reduce((sum, d) => sum + (d.total || 0), 0)
    };
  }, [chartData]);

  // Find peak values
  const peakValues = useMemo(() => {
    if (!Array.isArray(chartData) || chartData.length === 0) {
      return { spoofing: null, loitering: null };
    }

    let maxSpoofing = { value: -1, index: -1 };
    let maxLoitering = { value: -1, index: -1 };

    chartData.forEach((d, index) => {
      if (d.spoofing > maxSpoofing.value) {
        maxSpoofing = { value: d.spoofing, index };
      }
      if (d.loitering > maxLoitering.value) {
        maxLoitering = { value: d.loitering, index };
      }
    });

    return {
      spoofing:
        maxSpoofing.index >= 0
          ? { ...chartData[maxSpoofing.index], index: maxSpoofing.index }
          : null,
      loitering:
        maxLoitering.index >= 0
          ? { ...chartData[maxLoitering.index], index: maxLoitering.index }
          : null
    };
  }, [chartData]);

  // Mock vessel count (for normalization)
  const vesselCount = 1247;

  // Calculate baseline (average of all data points)
  const baselineValue = useMemo(() => {
    if (!Array.isArray(chartData) || chartData.length === 0) return 0;
    const sum = chartData.reduce((acc, d) => acc + (d.total || 0), 0);
    return Math.round(sum / chartData.length);
  }, [chartData]);

  // Detect spikes for annotations
  const spikeAnnotations = useMemo(() => {
    if (!Array.isArray(chartData) || chartData.length === 0) return [];
    const avgTotal = baselineValue;
    const threshold = avgTotal * 1.5;

    return chartData
      .map((d, index) => {
        if (d.total > threshold) {
          let annotation = '';
          if (d.spoofing > d.loitering && d.spoofing > 5) {
            annotation = 'Spoofing surge';
          } else if (d.loitering > d.spoofing && d.loitering > 8) {
            annotation = 'Loitering cluster';
          } else if (d.total > avgTotal * 2) {
            annotation = 'Anomaly spike';
          }
          return annotation
            ? { index, annotation, value: d.total, time: d.time }
            : null;
        }
        return null;
      })
      .filter(Boolean);
  }, [chartData, baselineValue]);

  // Generate insights summary
  const insightsSummary = useMemo(() => {
    if (!Array.isArray(chartData) || chartData.length === 0) return '';

    const avgTotal = baselineValue;
    const maxTotal = Math.max(...chartData.map((d) => d.total));
    const totalSpoofing = summaryTotals.spoofing;
    const totalLoitering = summaryTotals.loitering;

    const insights = [];

    if (maxTotal > avgTotal * 1.5) {
      insights.push(
        `Peak anomaly activity ${Math.round((maxTotal / avgTotal - 1) * 100)}% above baseline`
      );
    }

    if (totalSpoofing > totalLoitering) {
      insights.push(
        `Spoofing incidents dominate (${totalSpoofing} vs ${totalLoitering} loitering)`
      );
    } else if (totalLoitering > totalSpoofing * 1.2) {
      insights.push(`Loitering activity elevated (${totalLoitering} incidents detected)`);
    }

    if (spikeAnnotations.length > 0) {
      insights.push(
        `${spikeAnnotations.length} significant spike${
          spikeAnnotations.length > 1 ? 's' : ''
        } detected`
      );
    }

    const trend =
      chartData.length > 1
        ? chartData[chartData.length - 1].total > chartData[0].total
          ? 'increasing'
          : 'decreasing'
        : 'stable';
    insights.push(`Overall trend: ${trend}`);

    return insights.length > 0
      ? insights.join('. ') + '.'
      : 'No significant anomalies detected in this period.';
  }, [chartData, baselineValue, summaryTotals, spikeAnnotations]);

  // Normalize data if enabled
  const displayData = useMemo(() => {
    if (!normalized || !Array.isArray(chartData)) return chartData;

    return chartData.map((d) => ({
      ...d,
      // NOTE: keep numbers numeric (not strings) -> Recharts behaves better
      spoofing: vesselCount > 0 ? Number(((d.spoofing / vesselCount) * 100).toFixed(2)) : d.spoofing,
      loitering: vesselCount > 0 ? Number(((d.loitering / vesselCount) * 100).toFixed(2)) : d.loitering,
      total: vesselCount > 0 ? Number(((d.total / vesselCount) * 100).toFixed(2)) : d.total,
      other: vesselCount > 0 ? Number(((d.other / vesselCount) * 100).toFixed(2)) : d.other
    }));
  }, [chartData, normalized, vesselCount]);

  const aggregationSubtitle = timeFilter === '24h' ? 'Hourly aggregation' : 'Daily aggregation';

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0]?.payload;
      const fullTime = data?.fullTime || label;

      return (
        <div className="bg-slate-800/95 backdrop-blur-sm p-3 rounded-lg border border-cyan-500/30 shadow-xl min-w-[200px]">
          <p className="text-cyan-400 font-semibold mb-2 text-sm">{fullTime}</p>
          <div className="space-y-1">
            {payload.map((entry) => (
              <div key={entry.dataKey} className="flex justify-between items-center">
                <span className="text-gray-400 text-xs" style={{ color: entry.color }}>
                  {entry.name}:
                </span>
                <span className="font-semibold text-sm ml-2" style={{ color: entry.color }}>
                  {entry.value}
                </span>
              </div>
            ))}
          </div>
          {data && (
            <div className="mt-2 pt-2 border-t border-slate-600">
              <p className="text-xs text-gray-500 italic">
                {data.spoofing > data.loitering
                  ? 'Near Port Houston'
                  : data.loitering > 0
                  ? 'EEZ Boundary'
                  : 'Normal operations'}
              </p>
            </div>
          )}
        </div>
      );
    }
    return null;
  };

  const handleChartClick = (data) => {
    if (data && data.activePayload && data.activePayload[0]) {
      const clickedData = data.activePayload[0].payload;
      const clickedDataKey = data.activePayload[0].dataKey;

      let anomalyType = null;
      if (clickedDataKey === 'spoofing') anomalyType = 'spoofing';
      else if (clickedDataKey === 'loitering') anomalyType = 'loitering';

      if (anomalyType && onAnomalyFilter) {
        onAnomalyFilter({
          type: anomalyType,
          timestamp: clickedData.timestamp,
          time: clickedData.time
        });
      }

      if (onVesselHighlight && clickedData) {
        onVesselHighlight({
          timestamp: clickedData.timestamp,
          anomalyType
        });
      }

      if (onChartClick) onChartClick(clickedData);
    }
  };

  // Custom dot component for peak indicators
  const PeakDot = ({ cx, cy, payload, dataKey, peakValue }) => {
    if (!peakValue || !payload || payload.timestamp == null) return null;
    if (payload.timestamp !== peakValue.timestamp) return null;

    return (
      <g>
        <circle
          cx={cx}
          cy={cy}
          r={6}
          fill={dataKey === 'spoofing' ? '#ff4444' : '#ff8c00'}
          stroke="white"
          strokeWidth={2}
        />
        <circle
          cx={cx}
          cy={cy}
          r={8}
          fill={dataKey === 'spoofing' ? '#ff4444' : '#ff8c00'}
          opacity={0.3}
          className="animate-ping"
        />
      </g>
    );
  };

  // ✅ FIX: remove `key` from spread props (React warning)
  const renderPeakDotSpoofing = (props) => {
    const { key, ...rest } = props;
    return (
      <PeakDot
        key={key}
        {...rest}
        peakValue={peakValues.spoofing}
        dataKey="spoofing"
      />
    );
  };

  const renderPeakDotLoitering = (props) => {
    const { key, ...rest } = props;
    return (
      <PeakDot
        key={key}
        {...rest}
        peakValue={peakValues.loitering}
        dataKey="loitering"
      />
    );
  };

  return (
    <div className="bg-slate-800/30 backdrop-blur-sm border-t border-cyan-500/20 p-4">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h3 className="text-lg font-semibold text-cyan-400 flex items-center">
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
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

          {['24h', '7d', '30d'].map((filter) => (
            <button
              key={filter}
              onClick={() => setTimeFilter(filter)}
              className={`px-3 py-1 rounded-lg text-sm transition-all ${
                timeFilter === filter
                  ? 'bg-cyan-600/30 text-cyan-400 border border-cyan-500/50'
                  : 'bg-slate-700/30 text-gray-400 hover:bg-slate-600/30 border border-slate-600/30'
              }`}
            >
              {filter}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Row */}
      <div className="flex items-center justify-center space-x-4 mb-3 px-2">
        <div className="flex items-center space-x-2 px-3 py-1.5 bg-slate-800/50 rounded-lg border border-red-500/30">
          <div className="w-2 h-2 bg-red-500 rounded-full"></div>
          <span className="text-xs text-gray-400">Spoofing:</span>
          <span className="text-sm font-semibold text-red-400">
            {normalized ? `${((summaryTotals.spoofing / vesselCount) * 100).toFixed(2)}%` : summaryTotals.spoofing}
          </span>
        </div>

        <div className="flex items-center space-x-2 px-3 py-1.5 bg-slate-800/50 rounded-lg border border-orange-500/30">
          <div className="w-2 h-2 bg-orange-500 rounded-full"></div>
          <span className="text-xs text-gray-400">Loitering:</span>
          <span className="text-sm font-semibold text-orange-400">
            {normalized ? `${((summaryTotals.loitering / vesselCount) * 100).toFixed(2)}%` : summaryTotals.loitering}
          </span>
        </div>

        <div className="flex items-center space-x-2 px-3 py-1.5 bg-slate-800/50 rounded-lg border border-cyan-500/30">
          <div className="w-2 h-2 bg-cyan-500 rounded-full"></div>
          <span className="text-xs text-gray-400">Total:</span>
          <span className="text-sm font-semibold text-cyan-400">
            {normalized ? `${((summaryTotals.total / vesselCount) * 100).toFixed(2)}%` : summaryTotals.total}
          </span>
        </div>
      </div>

      {/* Insights Summary */}
      <div className="mb-3 px-2 py-2 bg-slate-800/40 rounded-lg border border-cyan-500/20">
        <div className="flex items-start space-x-2">
          <svg className="w-4 h-4 text-cyan-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-xs text-gray-300 leading-relaxed">{insightsSummary}</p>
        </div>
      </div>

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
                  ? {
                      value: 'Per 100 vessels',
                      angle: -90,
                      position: 'insideLeft',
                      fill: '#94a3b8',
                      fontSize: 10
                    }
                  : undefined
              }
            />
            <Tooltip content={<CustomTooltip />} />

            {showBaseline && (
              <ReferenceLine
                y={normalized ? Number(((baselineValue / vesselCount) * 100).toFixed(2)) : baselineValue}
                stroke="#64748b"
                strokeWidth={1.5}
                strokeDasharray="3 3"
                opacity={0.4}
                label={{
                  value: 'Expected baseline',
                  position: 'right',
                  fill: '#94a3b8',
                  fontSize: 10,
                  offset: 5
                }}
              />
            )}

            <Line
              type="monotone"
              dataKey="spoofing"
              stroke="#ff4444"
              strokeWidth={2}
              dot={renderPeakDotSpoofing} // ✅ FIXED
              activeDot={{ r: 6, stroke: '#ff4444', strokeWidth: 2, cursor: 'pointer' }}
              name="Spoofing"
              style={{ cursor: 'pointer' }}
            />

            <Line
              type="monotone"
              dataKey="loitering"
              stroke="#ff8c00"
              strokeWidth={2}
              dot={renderPeakDotLoitering} // ✅ FIXED
              activeDot={{ r: 6, stroke: '#ff8c00', strokeWidth: 2, cursor: 'pointer' }}
              name="Loitering"
              style={{ cursor: 'pointer' }}
            />

            <Line
              type="monotone"
              dataKey="other"
              stroke="#00d4ff"
              strokeWidth={2}
              dot={{ fill: '#00d4ff', strokeWidth: 0, r: 4 }}
              activeDot={{ r: 6, stroke: '#00d4ff', strokeWidth: 2, cursor: 'pointer' }}
              name="Other"
              style={{ cursor: 'pointer' }}
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
          <div className="w-3 h-3 bg-red-500 rounded-full"></div>
          <span className="text-xs text-gray-400">Spoofing</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 bg-orange-500 rounded-full"></div>
          <span className="text-xs text-gray-400">Loitering</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 bg-cyan-500 rounded-full"></div>
          <span className="text-xs text-gray-400">Other Anomalies</span>
        </div>
      </div>
    </div>
  );
};

export default BottomChart;
