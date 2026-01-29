import React, { useState } from 'react';
import { MapPin, Copy, X } from 'lucide-react';

const VesselLogs = ({
  vesselLogs: propVesselLogs = [],
  onVesselSelect,
  externalFilter,
  onFilterClear,
  externalMmsi = null,          // ✅ NEW: allow filtering directly by MMSI
  onExternalMmsiClear = null,   // ✅ NEW: clear MMSI filter from parent
}) => {
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [selectedVessel, setSelectedVessel] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const rowsPerPage = 10; // ✅ UI: 5 is too low; make it 10 by default

  // Apply external filter when provided (from chart click)
  React.useEffect(() => {
    if (externalFilter) {
      setFilter(externalFilter.type);
      setCurrentPage(1);
    }
  }, [externalFilter]);

  // Reset pagination when filter/search changes
  React.useEffect(() => {
    setCurrentPage(1);
  }, [filter, search, externalMmsi]);

  // Transform backend vessel logs to UI format
  const transformVesselLogs = (logs) => {
    if (!logs || logs.length === 0) return [];

    return logs.map((log, idx) => {
      let status = 'normal';
      if (log.spoofing_flag === true || log.spoofing_flag === 'true') status = 'spoofing';
      else if (log.loitering_flag === true || log.loitering_flag === 'true') status = 'loitering';

      const lat = typeof log.lat === 'number'
        ? `${log.lat.toFixed(1)}°${log.lat >= 0 ? 'N' : 'S'}`
        : (log.lat || 'N/A');

      const lon = typeof log.lon === 'number'
        ? `${Math.abs(log.lon).toFixed(1)}°${log.lon >= 0 ? 'E' : 'W'}`
        : (log.lon || 'N/A');

      let updated = 'N/A';
      if (log.timestamp) {
        try {
          const date = new Date(log.timestamp);
          updated = date.toLocaleTimeString();
        } catch {
          updated = String(log.timestamp);
        }
      }

      const mmsi = log.mmsi ?? null;
      const vesselNameRaw =
  log.vessel_name ??
  log.shipname ??
  log.ship_name ??
  log.name ??
  log.vessel ??
  log.callsign ??
  null;

const vesselName = (String(vesselNameRaw || "").trim()) || (mmsi ? `MMSI-${mmsi}` : `Vessel-${idx + 1}`);
return {
        id: `${mmsi || 'no-mmsi'}-${idx}`, // ✅ stable key
        name: vesselName,
        mmsi,
        type: log.vessel_type || 'Unknown',
        lat,
        lon,
        speed: log.sog !== undefined && log.sog !== null ? parseFloat(log.sog).toFixed(1) : '0.0',
        status,
        updated,
        destination: log.destination || 'Unknown',
        draft: log.draft ? `${log.draft}m` : 'N/A',
        originalData: log
      };
    });
  };

  const vessels = transformVesselLogs(propVesselLogs);

  const getStatusColor = (status) => {
    switch (status) {
      case 'normal': return 'bg-green-500 text-white';
      case 'loitering': return 'bg-yellow-400 text-black';
      case 'spoofing': return 'bg-red-500 text-white';
      default: return 'bg-gray-500 text-white';
    }
  };

  // ✅ Better search: match MMSI, vessel name, type
  const q = search.trim().toLowerCase().replace(/\s+/g, " ");


  const filteredVessels = vessels.filter(v => {
    const matchesStatus = (filter === 'all' || v.status === filter);

    const matchesExternalMmsi = externalMmsi
      ? String(v.mmsi || '') === String(externalMmsi)
      : true;

    const matchesSearch =
      !q ||
      (v.name || "").toLowerCase().replace(/\s+/g, " ").includes(q) ||
      (v.type || '').toLowerCase().includes(q) ||
      String(v.mmsi || '').includes(q);

    return matchesStatus && matchesExternalMmsi && matchesSearch;
  });

  // pagination (AFTER filtering)
  const totalPages = Math.ceil(filteredVessels.length / rowsPerPage);
  const startIndex = (currentPage - 1) * rowsPerPage;
  const currentVessels = filteredVessels.slice(startIndex, startIndex + rowsPerPage);

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(String(text));
    } catch {
      // ignore
    }
  };

  return (
    <div className="bg-slate-800/40 border border-cyan-500/30 rounded-xl p-6 relative">
      <h2 className="text-xl font-semibold text-cyan-400 mb-4">Vessel Logs</h2>

      {/* Filters */}
      <div className="flex flex-col gap-3 mb-4">
        <div className="flex items-center gap-3">
          <select
            className="bg-slate-700 text-gray-300 px-3 py-2 rounded-lg border border-slate-600"
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value);
              if (onFilterClear && externalFilter) onFilterClear();
            }}
          >
            <option value="all">All Status</option>
            <option value="normal">Normal</option>
            <option value="loitering">Loitering</option>
            <option value="spoofing">Spoofing</option>
          </select>

          <input
            type="text"
            placeholder="Search MMSI / vessel / type…"
            className="flex-1 bg-slate-700 text-gray-300 px-3 py-2 rounded-lg border border-slate-600"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {/* Active filters badges */}
        <div className="flex flex-wrap gap-2">
          {externalFilter && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-cyan-600/20 border border-cyan-500/50 rounded-lg">
              <span className="text-xs text-cyan-300">Chart filter:</span>
              <span className="text-xs font-semibold text-cyan-400 capitalize">{externalFilter.type}</span>
              <button
                onClick={() => {
                  setFilter('all');
                  if (onFilterClear) onFilterClear();
                }}
                className="text-cyan-300 hover:text-red-400 transition-colors"
                title="Clear chart filter"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {externalMmsi && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-700/40 border border-slate-600 rounded-lg">
              <span className="text-xs text-gray-300">MMSI:</span>
              <span className="text-xs font-semibold text-white font-mono">{externalMmsi}</span>
              <button
                onClick={() => onExternalMmsiClear?.()}
                className="text-gray-300 hover:text-red-400 transition-colors"
                title="Clear MMSI filter"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
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

                {/* ✅ MMSI as a clickable chip + copy */}
                <td className="px-4 py-2">
                  {vessel.mmsi ? (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        copyToClipboard(vessel.mmsi);
                      }}
                      className="inline-flex items-center gap-2 px-2 py-1 rounded bg-slate-700/60 border border-slate-600 hover:bg-slate-700 text-white font-mono text-xs"
                      title="Click to copy MMSI"
                    >
                      {vessel.mmsi}
                      <Copy className="w-3.5 h-3.5 opacity-70" />
                    </button>
                  ) : (
                    <span className="text-gray-500">N/A</span>
                  )}
                </td>

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

            {currentVessels.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-6 text-center text-gray-400">
                  No vessels match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      <div className="flex justify-between items-center mt-4 text-sm text-gray-300">
        <span>
          Showing {currentVessels.length} of {filteredVessels.length} • Page {currentPage} of {totalPages || 1}
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

      {/* Modal for Vessel Details (unchanged except stable id) */}
      {selectedVessel && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-900 border border-cyan-500/40 rounded-xl shadow-2xl p-6 w-full max-w-md relative">
            <button
              onClick={() => setSelectedVessel(null)}
              className="absolute top-3 right-3 text-gray-400 hover:text-red-400 transition-colors p-1"
              aria-label="Close modal"
            >
              ✕
            </button>

            <h3 className="text-lg font-bold text-cyan-400 mb-4 pr-8">{selectedVessel.name}</h3>
            <div className="space-y-3 text-sm text-gray-300">
              <div className="flex justify-between items-center">
                <span className="text-gray-400">MMSI:</span>
                <span className="font-mono text-white">{selectedVessel.mmsi ?? 'N/A'}</span>
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

            <div className="mt-6 flex flex-col sm:flex-row gap-3">
              <button
                onClick={() => {
                  onVesselSelect?.(selectedVessel.mmsi || selectedVessel.id);
                  setSelectedVessel(null);
                }}
                className="flex-1 bg-cyan-600 hover:bg-cyan-700 text-white py-2.5 rounded-lg transition-all flex items-center justify-center space-x-2"
              >
                <MapPin className="w-4 h-4" />
                <span>View on Map</span>
              </button>
              <button
                onClick={() => setSelectedVessel(null)}
                className="flex-1 bg-gray-700/50 hover:bg-gray-600 text-gray-300 py-2.5 rounded-lg transition-all border border-gray-600"
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
