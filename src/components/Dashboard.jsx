import React, { useState } from 'react';
import Sidebar from './Sidebar';
import MapView from './MapView';
import RightPanel from './RightPanel';
import BottomChart from './BottomChart';

const Dashboard = ({ onLogout }) => {
  const [activeView, setActiveView] = useState('dashboard');
  const [highlightedVesselId, setHighlightedVesselId] = useState(null);

  const handleAlertClick = (vesselId) => {
    setHighlightedVesselId(vesselId);
    // Auto-clear highlight after 5 seconds
    setTimeout(() => setHighlightedVesselId(null), 5000);
  };

  const handleVesselClick = (vessel) => {
    console.log('Vessel clicked:', vessel);
    // Future: Open vessel details modal
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-blue-900 text-white overflow-hidden">
      {/* Enhanced Header */}
      <header className="bg-slate-800/50 backdrop-blur-lg border-b border-cyan-500/20 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-to-br from-cyan-400 to-teal-600 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2L2 7v10c0 5.55 3.84 9.74 9 9.74s9-4.19 9-9.74V7L12 2z"/>
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-teal-400 bg-clip-text text-transparent">
                  LEVIATHAN
                </h1>
                <div className="text-xs text-gray-400">Maritime Surveillance Command Center</div>
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-6">
            <div className="flex items-center space-x-4 text-sm">
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-gray-300">SYSTEM ONLINE</span>
              </div>
              <div className="text-gray-400">|</div>
              <div className="flex items-center space-x-2">
                <svg className="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="text-gray-300">{new Date().toLocaleTimeString()}</span>
              </div>
            </div>
            <button
              onClick={onLogout}
              className="flex items-center space-x-2 px-4 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 rounded-lg transition-all duration-200 border border-red-500/20"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              <span>Logout</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="flex h-[calc(100vh-80px)]">
        <Sidebar activeView={activeView} setActiveView={setActiveView} />
        
        <div className="flex-1 flex flex-col">
          {/* Main map area */}
          <div className="flex-1 flex">
            <MapView 
              highlightedVesselId={highlightedVesselId}
              onVesselClick={handleVesselClick}
            />
            <RightPanel onAlertClick={handleAlertClick} />
          </div>
          
          {/* Bottom chart */}
          <BottomChart />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;