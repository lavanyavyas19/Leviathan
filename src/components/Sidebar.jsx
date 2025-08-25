import React, { useRef } from 'react';

const Sidebar = ({ activeView, setActiveView }) => {
  const fileInputRef = useRef(null);

  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '🎯' },
    { id: 'vessel-logs', label: 'Vessel Logs', icon: '🚢' },
    { id: 'anomaly-reports', label: 'Anomaly Reports', icon: '⚠️' },
    { id: 'heatmaps', label: 'Heatmaps', icon: '🗺️' },
    { id: 'playback', label: 'Playback', icon: '⏯️' },
    { id: 'reports-export', label: 'Reports/Export', icon: '📊' },
    { id: 'settings', label: 'Settings', icon: '⚙️' },
  ];

  const handleFileImport = (event) => {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          let data;
          if (file.name.endsWith('.json')) {
            data = JSON.parse(e.target.result);
          } else if (file.name.endsWith('.csv')) {
            // Simple CSV parsing - in production, use a proper CSV parser
            const lines = e.target.result.split('\n');
            const headers = lines[0].split(',');
            data = lines.slice(1).map(line => {
              const values = line.split(',');
              const obj = {};
              headers.forEach((header, index) => {
                obj[header.trim()] = values[index]?.trim();
              });
              return obj;
            });
          }
          
          console.log('Imported AIS Dataset:', data);
          // In a real implementation, this would update the vessel simulation
          alert(`Successfully imported ${data.length || Object.keys(data).length} records from ${file.name}`);
        } catch (error) {
          console.error('Error parsing file:', error);
          alert('Error parsing file. Please ensure it\'s a valid JSON or CSV file.');
        }
      };
      reader.readAsText(file);
    }
  };

  const triggerFileImport = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="w-64 bg-slate-800/50 backdrop-blur-lg border-r border-cyan-500/20 p-4">
      {/* Import Dataset Button */}
      <div className="mb-6">
        <button
          onClick={triggerFileImport}
          className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-gradient-to-r from-emerald-600/30 to-teal-600/30 hover:from-emerald-600/40 hover:to-teal-600/40 text-emerald-400 rounded-lg transition-all duration-200 border border-emerald-500/50 shadow-lg shadow-emerald-500/20"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <span className="font-medium">Import Dataset</span>
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json,.csv"
          onChange={handleFileImport}
          className="hidden"
        />
        <p className="text-xs text-gray-400 mt-1 text-center">
          Upload AIS data (JSON/CSV)
        </p>
      </div>

      {/* Navigation Menu */}
      <nav className="space-y-2">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveView(item.id)}
            className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ${
              activeView === item.id
                ? 'bg-gradient-to-r from-cyan-600/30 to-teal-600/30 border border-cyan-500/50 shadow-lg shadow-cyan-500/20'
                : 'hover:bg-slate-700/50 border border-transparent'
            }`}
          >
            <span className="text-lg">{item.icon}</span>
            <span className="font-medium">{item.label}</span>
            {activeView === item.id && (
              <div className="ml-auto w-2 h-2 bg-cyan-400 rounded-full animate-pulse"></div>
            )}
          </button>
        ))}
      </nav>

      {/* System Status */}
      <div className="mt-8 p-4 bg-slate-700/30 rounded-lg border border-slate-600/30">
        <h3 className="text-sm font-semibold text-gray-300 mb-3">Quick Stats</h3>
        <div className="space-y-2 text-xs">
          <div className="flex justify-between">
            <span className="text-gray-400">Active Vessels</span>
            <span className="text-cyan-400 font-mono">1,247</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Alerts Today</span>
            <span className="text-orange-400 font-mono">23</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Coverage</span>
            <span className="text-green-400 font-mono">98.7%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Data Sources</span>
            <span className="text-purple-400 font-mono">12</span>
          </div>
        </div>
      </div>

      {/* Data Import Status */}
      <div className="mt-4 p-3 bg-slate-700/20 rounded-lg border border-slate-600/20">
        <h4 className="text-xs font-semibold text-gray-300 mb-2">Data Sources</h4>
        <div className="space-y-1 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-gray-400">Live AIS Feed</span>
            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-400">Satellite Data</span>
            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-400">Radar Network</span>
            <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-400">Custom Dataset</span>
            <div className="w-2 h-2 bg-gray-500 rounded-full"></div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;