import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';

const BottomChart = () => {
  const [timeFilter, setTimeFilter] = useState('24h');
  const [chartData, setChartData] = useState([]);

  // Generate mock data based on time filter
  useEffect(() => {
    const generateData = () => {
      const now = new Date();
      let dataPoints = [];
      let intervals, stepSize, formatString;

      switch (timeFilter) {
        case '24h':
          intervals = 24;
          stepSize = 60 * 60 * 1000; // 1 hour
          formatString = 'HH:mm';
          break;
        case '7d':
          intervals = 7;
          stepSize = 24 * 60 * 60 * 1000; // 1 day
          formatString = 'MM/dd';
          break;
        case '30d':
          intervals = 30;
          stepSize = 24 * 60 * 60 * 1000; // 1 day
          formatString = 'MM/dd';
          break;
        default:
          intervals = 24;
          stepSize = 60 * 60 * 1000;
          formatString = 'HH:mm';
      }

      for (let i = intervals - 1; i >= 0; i--) {
        const time = new Date(now.getTime() - (i * stepSize));
        const baseAnomalies = Math.floor(Math.random() * 15) + 5;
        const spoofing = Math.floor(Math.random() * 8) + 1;
        const loitering = Math.floor(Math.random() * 12) + 3;
        
        dataPoints.push({
          time: time.toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit',
            ...(timeFilter !== '24h' && { 
              month: '2-digit', 
              day: '2-digit' 
            })
          }),
          total: baseAnomalies + spoofing + loitering,
          spoofing: spoofing,
          loitering: loitering,
          other: baseAnomalies,
          timestamp: time.getTime()
        });
      }

      return dataPoints;
    };

    setChartData(generateData());
  }, [timeFilter]);

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-slate-800/90 backdrop-blur-sm p-3 rounded-lg border border-cyan-500/30 shadow-xl">
          <p className="text-cyan-400 font-semibold mb-2">{label}</p>
          {payload.map((entry) => (
            <p key={entry.dataKey} style={{ color: entry.color }} className="text-sm">
              {entry.name}: {entry.value}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="h-64 bg-slate-800/30 backdrop-blur-sm border-t border-cyan-500/20 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-cyan-400 flex items-center">
          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          Anomaly Detection Trends
        </h3>

        <div className="flex space-x-2">
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

      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
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
            />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="spoofing"
              stroke="#ff4444"
              strokeWidth={2}
              dot={{ fill: '#ff4444', strokeWidth: 0, r: 4 }}
              activeDot={{ r: 6, stroke: '#ff4444', strokeWidth: 2 }}
              name="Spoofing"
            />
            <Line
              type="monotone"
              dataKey="loitering"
              stroke="#ff8c00"
              strokeWidth={2}
              dot={{ fill: '#ff8c00', strokeWidth: 0, r: 4 }}
              activeDot={{ r: 6, stroke: '#ff8c00', strokeWidth: 2 }}
              name="Loitering"
            />
            <Line
              type="monotone"
              dataKey="other"
              stroke="#00d4ff"
              strokeWidth={2}
              dot={{ fill: '#00d4ff', strokeWidth: 0, r: 4 }}
              activeDot={{ r: 6, stroke: '#00d4ff', strokeWidth: 2 }}
              name="Other"
            />
          </LineChart>
        </ResponsiveContainer>
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