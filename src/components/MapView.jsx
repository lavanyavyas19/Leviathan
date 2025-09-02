import React, { useState, useEffect, useRef } from 'react';

const MapView = ({ highlightedVesselId, onVesselClick }) => {
  const [vessels, setVessels] = useState([]);
  const [radarSweepAngle, setRadarSweepAngle] = useState(0);
  const [hoveredVessel, setHoveredVessel] = useState(null);
  const [playbackTime, setPlaybackTime] = useState(100); // 100% = current time
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRange, setPlaybackRange] = useState('24h');
  const mapRef = useRef(null);

  // Enhanced vessel data with AIS information
  useEffect(() => {
    const initialVessels = Array.from({ length: 15 }, (_, i) => {
      const vesselTypes = ['Cargo', 'Tanker', 'Fishing', 'Passenger', 'Tug'];
      const statuses = ['normal', 'loitering', 'spoofing'];
      const status = statuses[Math.floor(Math.random() * statuses.length)];
      
      return {
        id: i + 1,
        name: `${vesselTypes[Math.floor(Math.random() * vesselTypes.length)]}-${String(i + 1).padStart(3, '0')}`,
        mmsi: 366000000 + Math.floor(Math.random() * 999999),
        x: Math.random() * 600 + 50,
        y: Math.random() * 400 + 50,
        status: status,
        heading: Math.random() * 360,
        speed: Math.random() * 25 + 5,
        lastAnomaly: status !== 'normal' ? new Date(Date.now() - Math.random() * 3600000) : null,
        trail: [],
        route: generateRoute(),
        routeIndex: 0,
        vesselType: vesselTypes[Math.floor(Math.random() * vesselTypes.length)]
      };
    });
    setVessels(initialVessels);
  }, []);

  // Generate a route for vessel to follow
  const generateRoute = () => {
    const routePoints = [];
    const centerX = 400;
    const centerY = 300;
    const radius = 200 + Math.random() * 150;
    
    for (let i = 0; i < 20; i++) {
      const angle = (i / 20) * Math.PI * 2;
      routePoints.push({
        x: centerX + Math.cos(angle) * radius + (Math.random() - 0.5) * 100,
        y: centerY + Math.sin(angle) * radius + (Math.random() - 0.5) * 100
      });
    }
    return routePoints;
  };

  // Animation loop for vessels and radar
  useEffect(() => {
    const interval = setInterval(() => {
      setRadarSweepAngle(prev => (prev + 2) % 360);

      if (playbackTime === 100 || isPlaying) {
        setVessels(prev => prev.map(vessel => {
          const currentRoute = vessel.route[vessel.routeIndex];
          const nextRoute = vessel.route[(vessel.routeIndex + 1) % vessel.route.length];
          
          // Move towards next route point
          const dx = nextRoute.x - vessel.x;
          const dy = nextRoute.y - vessel.y;
          const distance = Math.sqrt(dx * dx + dy * dy);
          
          let newX = vessel.x;
          let newY = vessel.y;
          let newRouteIndex = vessel.routeIndex;
          
          if (distance < 10) {
            newRouteIndex = (vessel.routeIndex + 1) % vessel.route.length;
          } else {
            const moveSpeed = vessel.speed * 0.1;
            newX = vessel.x + (dx / distance) * moveSpeed;
            newY = vessel.y + (dy / distance) * moveSpeed;
          }

          // Update heading based on movement direction
          const newHeading = Math.atan2(dy, dx) * 180 / Math.PI;

          // Update trail with fading effect (10 minutes = 60 points at 10s intervals)
          const newTrail = [...vessel.trail, { 
            x: vessel.x, 
            y: vessel.y, 
            timestamp: Date.now() 
          }].slice(-60);

          return {
            ...vessel,
            x: newX,
            y: newY,
            heading: newHeading,
            routeIndex: newRouteIndex,
            trail: newTrail
          };
        }));
      }
    }, 100);

    return () => clearInterval(interval);
  }, [playbackTime, isPlaying]);

  const getVesselColor = (status) => {
    switch (status) {
      case 'normal': return '#00D4FF';
      case 'loitering': return '#FF8C00';
      case 'spoofing': return '#FF4444';
      default: return '#00D4FF';
    }
  };

  const getStatusGlow = (status, isHighlighted = false) => {
    const baseGlow = {
      'normal': 'drop-shadow-[0_0_8px_rgba(0,212,255,0.8)]',
      'loitering': 'drop-shadow-[0_0_8px_rgba(255,140,0,0.8)]',
      'spoofing': 'drop-shadow-[0_0_8px_rgba(255,68,68,0.8)]'
    }[status] || 'drop-shadow-[0_0_8px_rgba(0,212,255,0.8)]';
    
    return isHighlighted ? `${baseGlow} drop-shadow-[0_0_20px_rgba(255,255,255,1)]` : baseGlow;
  };

  const handleVesselClick = (vessel) => {
    onVesselClick?.(vessel);
  };

  const handlePlayback = () => {
    setIsPlaying(!isPlaying);
  };

  const zones = [
    { name: 'Restricted Zone Alpha', x: 150, y: 100, width: 120, height: 80, color: 'rgba(255, 0, 0, 0.2)' },
    { name: 'EEZ Boundary', x: 300, y: 200, width: 200, height: 150, color: 'rgba(255, 255, 0, 0.15)' },
    { name: 'Port Houston', x: 500, y: 350, width: 100, height: 60, color: 'rgba(0, 255, 0, 0.2)' }
  ];

  return (
    <div className="flex-1 p-6 relative">
      <div className="bg-slate-800/30 rounded-xl border border-cyan-500/30 h-full relative overflow-hidden">
        {/* Map Header */}
        <div className="absolute top-4 left-4 z-20 bg-slate-900/80 backdrop-blur-sm rounded-lg p-3 border border-cyan-500/30">
          <h2 className="text-lg font-semibold text-cyan-400 mb-2">Gulf of Mexico - Live View</h2>
          <div className="text-xs text-gray-400 space-y-1">
            <div>Lat: 25.5°N - 30.5°N</div>
            <div>Lng: 97.5°W - 82.5°W</div>
            <div className="flex items-center space-x-1 mt-2">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span>Real-time AIS Data</span>
            </div>
          </div>
        </div>

        {/* Enhanced Legend */}
        <div className="absolute top-4 right-4 z-20 bg-slate-900/80 backdrop-blur-sm rounded-lg p-3 border border-cyan-500/30">
          <h3 className="text-sm font-semibold text-gray-300 mb-2">Vessel Status</h3>
          <div className="space-y-1 text-xs">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-cyan-400 rounded-full"></div>
              <span className="text-gray-400">Normal Operation</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-orange-400 rounded-full"></div>
              <span className="text-gray-400">Loitering Detected</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-red-400 rounded-full"></div>
              <span className="text-gray-400">Spoofing Alert</span>
            </div>
          </div>
          <hr className="border-slate-600 my-2" />
          <h4 className="text-sm font-semibold text-gray-300 mb-1">Zones</h4>
          <div className="space-y-1 text-xs">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-2 bg-red-500/40 border border-red-500"></div>
              <span className="text-gray-400">Restricted</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-2 bg-yellow-500/30 border border-yellow-500"></div>
              <span className="text-gray-400">EEZ Boundary</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-2 bg-green-500/40 border border-green-500"></div>
              <span className="text-gray-400">Port Area</span>
            </div>
          </div>
        </div>

        {/* SVG Map Container */}
        <svg ref={mapRef} className="w-full h-full" viewBox="0 0 800 600">
          <defs>
            <radialGradient id="oceanGradient" cx="50%" cy="50%" r="70%">
              <stop offset="0%" stopColor="rgba(0, 50, 100, 0.3)" />
              <stop offset="100%" stopColor="rgba(0, 30, 60, 0.6)" />
            </radialGradient>
            
            <linearGradient id="radarSweep" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="rgba(0, 255, 255, 0)" />
              <stop offset="50%" stopColor="rgba(0, 255, 255, 0.3)" />
              <stop offset="100%" stopColor="rgba(0, 255, 255, 0)" />
            </linearGradient>
            <g id="vesselShape">
  {/* Hull */}
  <rect x="-10" y="-4" width="20" height="8" rx="2" ry="2"
        fill="currentColor" stroke="white" strokeWidth="0.8"/>

  {/* Bow */}
  <polygon points="10,-4 10,4 18,0"
           fill="currentColor" stroke="white" strokeWidth="0.8"/>

  {/* Bridge */}
  <rect x="-4" y="-3" width="4" height="6" fill="white" />
</g>
</defs>

          {/* Ocean background */}
          <rect width="800" height="600" fill="url(#oceanGradient)" />

          {/* Zones */}
          {zones.map((zone, index) => (
            <g key={`zone-${index}`}>
              <rect
                x={zone.x}
                y={zone.y}
                width={zone.width}
                height={zone.height}
                fill={zone.color}
                stroke={zone.color.replace('0.2', '0.6').replace('0.15', '0.5').replace('0.4', '0.8')}
                strokeWidth="2"
                strokeDasharray="5,5"
              />
              <text
                x={zone.x + zone.width / 2}
                y={zone.y + zone.height / 2}
                textAnchor="middle"
                dominantBaseline="middle"
                fill="rgba(255,255,255,0.8)"
                fontSize="10"
                className="font-mono"
              >
                {zone.name}
              </text>
            </g>
          ))}

          {/* Radar grid */}
          {Array.from({ length: 6 }, (_, i) => (
            <circle
              key={`grid-${i}`}
              cx="400"
              cy="300"
              r={(i + 1) * 80}
              fill="none"
              stroke="rgba(0, 255, 255, 0.2)"
              strokeWidth="1"
              strokeDasharray="5,5"
            />
          ))}

          {/* Radar sweep */}
          <g transform={`rotate(${radarSweepAngle} 400 300)`}>
            <line
              x1="400"
              y1="300"
              x2="800"
              y2="300"
              stroke="url(#radarSweep)"
              strokeWidth="60"
              opacity="0.6"
            />
          </g>

          {/* Vessel trails with fade effect */}
          {vessels.map(vessel => (
            <g key={`trail-${vessel.id}`}>
              {vessel.trail.map((point, index) => {
                const age = Date.now() - point.timestamp;
                const maxAge = 600000; // 10 minutes
                const opacity = Math.max(0, 1 - (age / maxAge)) * 0.6;
                
                return (
                  <circle
                    key={`trail-point-${vessel.id}-${index}`}
                    cx={point.x}
                    cy={point.y}
                    r={2 * opacity + 0.5}
                    fill={getVesselColor(vessel.status)}
                    opacity={opacity}
                  />
                );
              })}
            </g>
          ))}

          {/* Vessels with enhanced graphics */}
          {vessels.map(vessel => {
            const isHighlighted = highlightedVesselId === vessel.id;
            return (
              <g 
                key={vessel.id} 
                transform={`translate(${vessel.x}, ${vessel.y}) rotate(${vessel.heading})`}
                style={{ cursor: 'pointer' }}
                className={highlightedVesselId === vessel.id ? "scale-125 drop-shadow-[0_0_20px_rgba(0,255,255,1)]" : ""}
                onClick={() => handleVesselClick(vessel)}
                onMouseEnter={() => setHoveredVessel(vessel)}
                onMouseLeave={() => setHoveredVessel(null)}
              >
                <use 
                  href="#vesselShape" 
                  fill={getVesselColor(vessel.status)}
                  className={getStatusGlow(vessel.status, isHighlighted)}
                  transform={isHighlighted ? 'scale(1.5)' : 'scale(1)'}
                />
                
                <text
                  x="16"
                  y="-2"
                  fill={getVesselColor(vessel.status)}
                  fontSize="9"
                  dominantBaseline="middle"
                  className="font-mono font-semibold"
                >
                  {vessel.name}
                </text>
                
                <text
                  x="16"
                  y="8"
                  fill="rgba(255,255,255,0.7)"
                  fontSize="7"
                  dominantBaseline="middle"
                  className="font-mono"
                >
                  {vessel.speed.toFixed(1)} kts
                </text>
              </g>
            );
          })}

          {/* Coastline */}
          <path
            d="M 50 50 Q 200 30 400 50 Q 600 70 750 50 L 750 100 Q 600 120 400 100 Q 200 80 50 100 Z"
            fill="rgba(101, 163, 13, 0.3)"
            stroke="rgba(101, 163, 13, 0.6)"
            strokeWidth="2"
          />
        </svg>

        {/* Hover Tooltip */}
        {hoveredVessel && (
          <div className="absolute z-30 bg-slate-900/95 backdrop-blur-sm border border-cyan-500/50 rounded-lg p-3 pointer-events-none shadow-xl">
            <div className="text-cyan-400 font-semibold text-sm">{hoveredVessel.name}</div>
            <div className="text-xs text-gray-300 mt-1 space-y-1">
              <div>MMSI: <span className="font-mono">{hoveredVessel.mmsi}</span></div>
              <div>Speed: <span className="font-mono">{hoveredVessel.speed.toFixed(1)} kts</span></div>
              <div>Heading: <span className="font-mono">{Math.round(hoveredVessel.heading)}°</span></div>
              <div>Type: <span className="font-mono">{hoveredVessel.vesselType}</span></div>
              {hoveredVessel.lastAnomaly && (
                <div className="text-orange-400">
                  Last Alert: {hoveredVessel.lastAnomaly.toLocaleTimeString()}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Playback Controls */}
        <div className="absolute bottom-4 left-4 right-4 z-20 bg-slate-900/80 backdrop-blur-sm rounded-lg p-3 border border-cyan-500/30">
          <div className="flex items-center space-x-4">
            <button
              onClick={handlePlayback}
              className="flex items-center space-x-2 px-3 py-2 bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-400 rounded-lg transition-all border border-cyan-500/30"
            >
              {isPlaying ? '⏸️' : '▶️'}
              <span className="text-sm">{isPlaying ? 'Pause' : 'Play'}</span>
            </button>

            <div className="flex items-center space-x-2 text-sm">
              <span className="text-gray-400">Range:</span>
              {['24h', '7d', '30d'].map((range) => (
                <button
                  key={range}
                  onClick={() => setPlaybackRange(range)}
                  className={`px-2 py-1 rounded text-xs transition-all ${
                    playbackRange === range
                      ? 'bg-cyan-600/30 text-cyan-400 border border-cyan-500/50'
                      : 'text-gray-400 hover:text-cyan-400'
                  }`}
                >
                  {range}
                </button>
              ))}
            </div>

            <div className="flex-1 mx-4">
              <input
                type="range"
                min="0"
                max="100"
                value={playbackTime}
                onChange={(e) => setPlaybackTime(parseInt(e.target.value))}
                className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer slider"
              />
            </div>

            <div className="text-xs text-gray-400 min-w-fit">
              {playbackTime === 100 ? 'Live' : `${playbackTime}% Complete`}
            </div>
          </div>
        </div>

        {/* Map Controls */}
        <div className="absolute bottom-20 left-4 z-20 flex flex-col space-y-2">
          <button className="w-10 h-10 bg-slate-800/80 hover:bg-slate-700/80 border border-cyan-500/30 rounded-lg flex items-center justify-center text-cyan-400 transition-all">
            +
          </button>
          <button className="w-10 h-10 bg-slate-800/80 hover:bg-slate-700/80 border border-cyan-500/30 rounded-lg flex items-center justify-center text-cyan-400 transition-all">
            −
          </button>
          <button className="w-10 h-10 bg-slate-800/80 hover:bg-slate-700/80 border border-cyan-500/30 rounded-lg flex items-center justify-center text-cyan-400 transition-all">
            🎯
          </button>
        </div>
      </div>
    </div>
  );
};

export default MapView;
