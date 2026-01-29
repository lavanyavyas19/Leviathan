import React, { useState } from 'react';
import Sidebar from './Sidebar';
import MapView from './MapView';
import RightPanel from './RightPanel';
import BottomChart from './BottomChart';
import VesselLogs from './VesselLogs';

const Dashboard = ({ onLogout }) => {
  const [activeView, setActiveView] = useState('dashboard');
  const [isPanelOpen, setIsPanelOpen] = useState(true);
  const [datasetUploaded, setDatasetUploaded] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [vesselLogs, setVesselLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [highlightedVesselId, setHighlightedVesselId] = useState(null);
  const [vesselLogsFilter, setVesselLogsFilter] = useState(null); // For filtering from chart clicks

  return (
    <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-blue-900 text-white min-h-screen flex flex-col">
      
      {/* ===== Header ===== */}
      <header className="bg-slate-800/50 backdrop-blur-lg border-b border-cyan-500/20 p-4 sticky top-0 z-50">
        <div className="flex justify-between items-center">
          <h1 className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-teal-400 bg-clip-text text-transparent">
            LEVIATHAN
          </h1>
          <div className="flex items-center space-x-4">
            {/* Toggle Right Panel (only in dashboard view) */}
            {activeView === 'dashboard' && (
              <button
                onClick={() => setIsPanelOpen(!isPanelOpen)}
                className="px-4 py-2 flex items-center space-x-2 
                           bg-slate-800/40 hover:bg-slate-700/60 
                           border border-cyan-500/30 rounded-lg 
                           text-cyan-400 transition-all duration-300 
                           shadow-md hover:shadow-cyan-500/30"
              >
                <svg
                  className={`w-5 h-5 transition-transform duration-300 ${
                    isPanelOpen ? "rotate-180 text-cyan-300" : "rotate-0 text-cyan-400"
                  }`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                <span className="text-sm font-medium tracking-wide">
                  {isPanelOpen ? "Hide Panel" : "Show Panel"}
                </span>
                {isPanelOpen && (
                  <span className="ml-2 w-2 h-2 bg-cyan-400 rounded-full animate-pulse"></span>
                )}
              </button>
            )}

            {/* Logout */}
            <button
              onClick={onLogout}
              className="px-4 py-2 bg-red-600/20 hover:bg-red-600/30 
                         text-red-400 rounded-lg border border-red-500/20"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* ===== Main Content ===== */}
      <div className="flex flex-1 overflow-y-auto">
        
        {/* Sidebar */}
        <Sidebar 
          activeView={activeView} 
          setActiveView={setActiveView} 
          setDatasetUploaded={setDatasetUploaded}
          datasetUploaded={datasetUploaded}
          setJobId={setJobId}
          setAlerts={setAlerts}
          setVesselLogs={setVesselLogs}
          setStats={setStats}
        />

        {/* ===== Page Content Area ===== */}
        <main className="flex-1 flex flex-col p-6 gap-6">
          
          {/* === Dashboard View === */}
          {activeView === 'dashboard' && (
            <>
              <div className="flex flex-1 relative gap-6">
                {/* Map View */}
                <div className="flex-1 transition-all duration-300">
                  <MapView 
                    highlightedVesselId={highlightedVesselId}
                    onVesselClick={(vessel) => setHighlightedVesselId(vessel?.id)}
                  />
                </div>

                {/* Right Panel */}
                {isPanelOpen && (
                  <div className="w-[350px] transition-all duration-300 flex-shrink-0">
                    <RightPanel 
                      datasetUploaded={datasetUploaded}
                      jobId={jobId}
                      alerts={alerts}
                      stats={stats}
                      onAlertClick={(vesselId) => setHighlightedVesselId(vesselId)}
                    />
                  </div>
                )}
              </div>
            </>
          )}

          {/* === Anomaly Reports View === */}
          {activeView === 'anomaly-reports' && (
            <div className="flex-1 bg-slate-800/40 rounded-xl border border-cyan-500/30 p-4 shadow-lg shadow-cyan-500/10">
              <BottomChart
                jobId={jobId}  // ✅ REQUIRED for real data
                onChartClick={(data) => {
                  setActiveView('dashboard');
                }}  onAnomalyFilter={(filter) => {
                  // Filter vessels by anomaly type and navigate to vessel logs
                  setVesselLogsFilter(filter);
                  setActiveView('vessel-logs');
                }}
                onVesselHighlight={(data) => {
                  // Highlight vessels on map (would need actual vessel IDs in real implementation)
                  // For now, just navigate to dashboard
                  setActiveView('dashboard');
                }}
              />
            </div>
          )}

          {/* === Other Views === */}
          {activeView === 'heatmaps' && (
            <div className="flex-1 flex items-center justify-center text-gray-400">
              Heatmaps view coming soon...
            </div>
          )}

          {activeView === 'playback' && (
            <div className="flex-1 flex items-center justify-center text-gray-400">
              Playback view coming soon...
            </div>
          )}

          {activeView === 'reports-export' && (
            <div className="flex-1 flex items-center justify-center text-gray-400">
              Reports & Export view coming soon...
            </div>
          )}

          {activeView === 'settings' && (
            <div className="flex-1 flex items-center justify-center text-gray-400">
              Settings view coming soon...
            </div>
          )}

          {activeView === 'vessel-logs' && (
            <VesselLogs 
              vesselLogs={vesselLogs}
              onVesselSelect={(id) => {
                setHighlightedVesselId(id);
                setActiveView('dashboard');
              }}
              externalFilter={vesselLogsFilter}
              onFilterClear={() => setVesselLogsFilter(null)}
            />
          )}
          
        </main>
      </div>
    </div>
  );
};

export default Dashboard;