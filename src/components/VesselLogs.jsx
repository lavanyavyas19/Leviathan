import React, { useState } from 'react';
import { MapPin } from 'lucide-react';

const VesselLogs = ({ onVesselSelect, externalFilter, onFilterClear }) => {
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [selectedVessel, setSelectedVessel] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const rowsPerPage = 5;

  // Apply external filter when provided (from chart click)
  React.useEffect(() => {
    if (externalFilter) {
      setFilter(externalFilter.type);
      setCurrentPage(1); // Reset to first page
    }
  }, [externalFilter]);

  const vessels = [
    { id: 1, name: 'MV-ATLANTIC-STAR', mmsi: 366123456, type: 'Cargo', lat: '27.5°N', lon: '94.2°W', speed: 12.5, status: 'normal', updated: '10:32:21', destination: 'Port Houston', draft: '12.4m' },
    { id: 2, name: 'GULF-RUNNER-07', mmsi: 366234567, type: 'Tanker', lat: '28.1°N', lon: '92.8°W', speed: 0.0, status: 'loitering', updated: '10:28:17', destination: 'Anchorage', draft: '15.7m' },
    { id: 3, name: 'OCEAN-BREEZE-12', mmsi: 366345678, type: 'Fishing', lat: '26.9°N', lon: '90.5°W', speed: 19.2, status: 'spoofing', updated: '10:21:43', destination: 'Unknown', draft: '6.3m' },
    { id: 4, name: 'PACIFIC-VOYAGER', mmsi: 366456789, type: 'Passenger', lat: '29.2°N', lon: '91.1°W', speed: 16.3, status: 'normal', updated: '10:35:50', destination: 'New Orleans', draft: '8.2m' },
    { id: 5, name: 'TIDE-MASTER-21', mmsi: 366567890, type: 'Tug', lat: '28.6°N', lon: '93.4°W', speed: 5.7, status: 'loitering', updated: '10:40:12', destination: 'Oil Rig Bravo', draft: '4.5m' },
    { id: 6, name: 'HORIZON-SPIRIT', mmsi: 366678901, type: 'Cargo', lat: '27.8°N', lon: '95.1°W', speed: 13.9, status: 'normal', updated: '10:36:59', destination: 'Corpus Christi', draft: '11.0m' },
    { id: 7, name: 'SEA-HAWK-03', mmsi: 366789012, type: 'Fishing', lat: '26.7°N', lon: '89.9°W', speed: 7.8, status: 'spoofing', updated: '10:25:10', destination: 'Unknown', draft: '5.8m' },
    { id: 8, name: 'CARIBBEAN-PEARL', mmsi: 366890123, type: 'Passenger', lat: '29.0°N', lon: '90.3°W', speed: 18.7, status: 'normal', updated: '10:45:03', destination: 'Miami', draft: '9.5m' },
    { id: 9, name: 'NORTH-WAVE', mmsi: 366901234, type: 'Tanker', lat: '28.3°N', lon: '94.7°W', speed: 0.0, status: 'loitering', updated: '10:48:27', destination: 'Anchorage', draft: '16.2m' },
    { id: 10, name: 'SOUTHERN-CROSS', mmsi: 367012345, type: 'Cargo', lat: '27.2°N', lon: '93.8°W', speed: 14.8, status: 'normal', updated: '10:50:11', destination: 'Mobile Port', draft: '10.9m' },
  ];
  
  const getStatusColor = (status) => {
    switch (status) {
      case 'normal': return 'bg-green-500 text-white';
      case 'loitering': return 'bg-yellow-400 text-black';
      case 'spoofing': return 'bg-red-500 text-white';
      default: return 'bg-gray-500 text-white';
    }
  };

  // filtering first
  const filteredVessels = vessels.filter(v => 
    (filter === 'all' || v.status === filter) &&
    (v.name.toLowerCase().includes(search.toLowerCase()) || 
     String(v.mmsi).includes(search))
  );

  // pagination logic (AFTER filtering)
  const totalPages = Math.ceil(filteredVessels.length / rowsPerPage);
  const startIndex = (currentPage - 1) * rowsPerPage;
  const currentVessels = filteredVessels.slice(startIndex, startIndex + rowsPerPage);

  return (
    <div className="bg-slate-800/40 border border-cyan-500/30 rounded-xl p-6 relative">
      <h2 className="text-xl font-semibold text-cyan-400 mb-4">Vessel Logs</h2>

      {/* Filters */}
      <div className="flex items-center space-x-4 mb-4">
        <select 
          className="bg-slate-700 text-gray-300 px-3 py-2 rounded-lg border border-slate-600"
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            if (onFilterClear && externalFilter) {
              onFilterClear();
            }
          }}
        >
          <option value="all">All Status</option>
          <option value="normal">Normal</option>
          <option value="loitering">Loitering</option>
          <option value="spoofing">Spoofing</option>
        </select>
        <input 
          type="text" 
          placeholder="Search vessel..."
          className="flex-1 bg-slate-700 text-gray-300 px-3 py-2 rounded-lg border border-slate-600"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {externalFilter && (
          <div className="flex items-center space-x-2 px-3 py-2 bg-cyan-600/20 border border-cyan-500/50 rounded-lg">
            <span className="text-xs text-cyan-300">Filtered from chart:</span>
            <span className="text-xs font-semibold text-cyan-400 capitalize">{externalFilter.type}</span>
            <button
              onClick={() => {
                setFilter('all');
                if (onFilterClear) onFilterClear();
              }}
              className="text-cyan-400 hover:text-red-400 transition-colors ml-2"
              title="Clear filter"
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left text-gray-300">
          <thead className="text-xs uppercase bg-slate-700 text-gray-400">
            <tr>
              <th className="px-4 py-3">Vessel</th>
              <th className="px-4 py-3">MMSI</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Lat</th>
              <th className="px-4 py-3">Lon</th>
              <th className="px-4 py-3">Speed</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Updated</th>
            </tr>
          </thead>
          <tbody>
            {currentVessels.map(vessel => (
              <tr 
                key={vessel.id} 
                className="border-b border-slate-600 hover:bg-slate-700/40 cursor-pointer"
                onClick={() => setSelectedVessel(vessel)}
              >
                <td className="px-4 py-2 font-semibold">{vessel.name}</td>
                <td className="px-4 py-2">{vessel.mmsi}</td>
                <td className="px-4 py-2">{vessel.type}</td>
                <td className="px-4 py-2">{vessel.lat}</td>
                <td className="px-4 py-2">{vessel.lon}</td>
                <td className="px-4 py-2">{vessel.speed} kts</td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-1 rounded text-xs font-bold ${getStatusColor(vessel.status)}`}>
                    {vessel.status.toUpperCase()}
                  </span>
                </td>
                <td className="px-4 py-2">{vessel.updated}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      <div className="flex justify-between items-center mt-4 text-sm text-gray-300">
        <span>
          Page {currentPage} of {totalPages || 1}
        </span>
        <div className="space-x-2">
          <button 
            disabled={currentPage === 1}
            onClick={() => setCurrentPage(prev => prev - 1)}
            className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 rounded"
          >
            Prev
          </button>
          <button 
            disabled={currentPage === totalPages || totalPages === 0}
            onClick={() => setCurrentPage(prev => prev + 1)}
            className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 rounded"
          >
            Next
          </button>
        </div>
      </div>

      {/* Modal for Vessel Details */}
      {selectedVessel && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-900 border border-cyan-500/40 rounded-xl shadow-2xl p-6 w-full max-w-md relative">
            {/* Close Button */}
            <button 
              onClick={() => setSelectedVessel(null)} 
              className="absolute top-3 right-3 text-gray-400 hover:text-red-400 transition-colors p-1"
              aria-label="Close modal"
            >
              ✕
            </button>

            {/* Vessel Details */}
            <h3 className="text-lg font-bold text-cyan-400 mb-4 pr-8">{selectedVessel.name}</h3>
            <div className="space-y-3 text-sm text-gray-300">
              <div className="flex justify-between items-center">
                <span className="text-gray-400">MMSI:</span>
                <span className="font-mono text-white">{selectedVessel.mmsi}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Type:</span>
                <span className="text-white">{selectedVessel.type}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Coordinates:</span>
                <span className="font-mono text-white">{selectedVessel.lat}, {selectedVessel.lon}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Speed:</span>
                <span className="font-mono text-white">{selectedVessel.speed} kts</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Status:</span>
                <span className={`px-2 py-1 rounded text-xs font-bold ${getStatusColor(selectedVessel.status)}`}>
                  {selectedVessel.status.toUpperCase()}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Destination:</span>
                <span className="text-white">{selectedVessel.destination}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Draft:</span>
                <span className="text-white">{selectedVessel.draft}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Last Update:</span>
                <span className="font-mono text-white">{selectedVessel.updated}</span>
              </div>
            </div>

            {/* Actions */}
            <div className="mt-6 flex flex-col sm:flex-row gap-3">
              <button 
                onClick={() => {
                  onVesselSelect?.(selectedVessel.id);
                  setSelectedVessel(null);
                }}
                className="flex-1 bg-cyan-600 hover:bg-cyan-700 text-white py-2.5 rounded-lg transition-all flex items-center justify-center space-x-2 focus:outline-none focus:ring-2 focus:ring-cyan-400 focus:ring-offset-2 focus:ring-offset-slate-900"
              >
                <MapPin className="w-4 h-4" aria-hidden="true" />
                <span>View on Map</span>
              </button>
              <button 
                onClick={() => setSelectedVessel(null)}
                className="flex-1 bg-gray-700/50 hover:bg-gray-600 text-gray-300 py-2.5 rounded-lg transition-all border border-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-2 focus:ring-offset-slate-900"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default VesselLogs;
