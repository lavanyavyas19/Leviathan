import React, { useRef } from 'react';

const Sidebar = ({ activeView, setActiveView }) => {
  const fileInputRef = useRef(null);

  // Define menu items here
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'vessel-logs', label: 'Vessel Logs' },
    { id: 'anomaly-reports', label: 'Anomaly Reports' },
    { id: 'heatmaps', label: 'Heatmaps' },
    { id: 'playback', label: 'Playback' },
    { id: 'reports-export', label: 'Reports/Export' },
    { id: 'settings', label: 'Settings' },
  ];
  
  // Handle dataset import
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
            // Simple CSV parsing - in production use PapaParse
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
          alert(`Successfully imported ${data.length || Object.keys(data).length} records from ${file.name}`);
        } catch (error) {
          console.error('Error parsing file:', error);
          alert('Error parsing file. Please make sure it’s a valid JSON or CSV file.');
        }
      };
      reader.readAsText(file);
    }
  };

  const triggerFileImport = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="w-64 bg-slate-800/50 backdrop-blur-lg border-r border-cyan-500/20 p-4 flex flex-col">
      {/* Import Dataset Button */}
      <div className="mb-6">
        <button
          onClick={triggerFileImport}
          className="w-full flex items-center justify-center space-x-2 px-4 py-3 
                     bg-gradient-to-r from-emerald-600/30 to-teal-600/30 
                     hover:from-emerald-600/40 hover:to-teal-600/40 
                     text-emerald-400 rounded-lg transition-all duration-200 
                     border border-emerald-500/50 shadow-lg shadow-emerald-500/20"
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
      <nav className="space-y-2 flex-1">
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
            <span className="font-medium">{item.label}</span>
            {activeView === item.id && (
              <div className="ml-auto w-2 h-2 bg-cyan-400 rounded-full animate-pulse"></div>
            )}
          </button>
        ))}
      </nav>
    </div>
  );
};

export default Sidebar;
