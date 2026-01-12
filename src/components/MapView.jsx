import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { ZoomIn, ZoomOut, RotateCcw, Play, Pause, X, Layers, Info, Menu } from 'lucide-react';
import { project, haversineNm, nmToPixels, MAP_WIDTH, MAP_HEIGHT, BOUNDARY_MARGIN } from '../utils/mapProjection';

// Ports configuration
const PORTS = [
  { id: 'houston', name: 'Port of Houston', lat: 29.73, lon: -95.27, influenceNm: 20 },
  { id: 'new_orleans', name: 'Port of New Orleans', lat: 29.95, lon: -90.07, influenceNm: 18 },
  { id: 'corpus', name: 'Port of Corpus Christi', lat: 27.80, lon: -97.40, influenceNm: 18 },
  { id: 'tampa', name: 'Port of Tampa Bay', lat: 27.95, lon: -82.45, influenceNm: 16 },
  { id: 'mobile', name: 'Port of Mobile', lat: 30.70, lon: -88.04, influenceNm: 14 }
];

const MapView = ({ highlightedVesselId, onVesselClick }) => {
  const [vessels, setVessels] = useState([]);
  const [radarSweepAngle, setRadarSweepAngle] = useState(0);
  const [hoveredVessel, setHoveredVessel] = useState(null);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });
  const [playbackTime, setPlaybackTime] = useState(100); // 100% = latest timestamp in dataset
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRange, setPlaybackRange] = useState('24h');
  const [zoom, setZoom] = useState(1);
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, width: 800, height: 600 });
  const [focusMode, setFocusMode] = useState(false);
  const [vesselLatLon, setVesselLatLon] = useState({});
  const [layersVisible, setLayersVisible] = useState({
    ports: true,
    portInfluence: true,
    eezBoundary: false,
    restrictedAreas: false,
    evidenceOverlays: false
  });
  const [showLayersPanel, setShowLayersPanel] = useState(false);
  const [showLegendPanel, setShowLegendPanel] = useState(false);
  const [showLiveViewPanel, setShowLiveViewPanel] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const mapRef = useRef(null);
  const svgRef = useRef(null);
  const prevHighlightedId = useRef(null);
  const dragThreshold = useRef(5); // pixels to move before considering it a drag
  const hasMovedDuringDrag = useRef(false);

  // Generate a route for vessel to follow
  const generateRoute = (startX = null, startY = null) => {
    const routePoints = [];
    const centerX = startX ?? 400;
    const centerY = startY ?? 300;
    const radius = 200 + Math.random() * 150;
    
    for (let i = 0; i < 20; i++) {
      const angle = (i / 20) * Math.PI * 2;
      const randomOffset = (Math.random() - 0.5) * Math.min(80, radius * 0.4);
      let x = centerX + Math.cos(angle) * radius + randomOffset;
      let y = centerY + Math.sin(angle) * radius + randomOffset;
      
      // Clamp route points to map bounds
      x = Math.max(BOUNDARY_MARGIN, Math.min(MAP_WIDTH - BOUNDARY_MARGIN, x));
      y = Math.max(BOUNDARY_MARGIN, Math.min(MAP_HEIGHT - BOUNDARY_MARGIN, y));
      
      routePoints.push({ x, y });
    }
    return routePoints;
  };

  // Project ports to map coordinates
  const projectedPorts = useMemo(() => {
    try {
      return PORTS.map(port => {
        const coords = project(port.lat, port.lon);
        return {
          ...port,
          x: coords.x,
          y: coords.y,
          influenceRadius: nmToPixels(port.influenceNm)
        };
      });
    } catch (error) {
      console.error('Error projecting ports:', error);
      return [];
    }
  }, []);

  // Enhanced vessel data with AIS information - matching VesselLogs data structure
  useEffect(() => {
    // Create vessels that match VesselLogs for better integration
    const vesselLogsData = [
      { id: 1, name: 'MV-ATLANTIC-STAR', mmsi: 366123456, type: 'Cargo', status: 'normal', speed: 12.5, lat: 27.5, lon: -94.2 },
      { id: 2, name: 'GULF-RUNNER-07', mmsi: 366234567, type: 'Tanker', status: 'loitering', speed: 0.0, lat: 28.1, lon: -92.8 },
      { id: 3, name: 'OCEAN-BREEZE-12', mmsi: 366345678, type: 'Fishing', status: 'spoofing', speed: 19.2, lat: 26.9, lon: -90.5 },
      { id: 4, name: 'PACIFIC-VOYAGER', mmsi: 366456789, type: 'Passenger', status: 'normal', speed: 16.3, lat: 29.2, lon: -91.1 },
      { id: 5, name: 'TIDE-MASTER-21', mmsi: 366567890, type: 'Tug', status: 'loitering', speed: 5.7, lat: 28.6, lon: -93.4 },
      { id: 6, name: 'HORIZON-SPIRIT', mmsi: 366678901, type: 'Cargo', status: 'normal', speed: 13.9, lat: 27.8, lon: -95.1 },
      { id: 7, name: 'SEA-HAWK-03', mmsi: 366789012, type: 'Fishing', status: 'spoofing', speed: 7.8, lat: 26.7, lon: -89.9 },
      { id: 8, name: 'CARIBBEAN-PEARL', mmsi: 366890123, type: 'Passenger', status: 'normal', speed: 18.7, lat: 29.0, lon: -90.3 },
      { id: 9, name: 'NORTH-WAVE', mmsi: 366901234, type: 'Tanker', status: 'loitering', speed: 0.0, lat: 28.3, lon: -94.7 },
      { id: 10, name: 'SOUTHERN-CROSS', mmsi: 367012345, type: 'Cargo', status: 'normal', speed: 14.8, lat: 27.2, lon: -93.8 },
    ];

    const initialVessels = vesselLogsData.map((logData) => {
      // Project lat/lon to map coordinates
      const projected = project(logData.lat, logData.lon);
      
      // Ensure initial position is within map bounds
      const x = Math.max(BOUNDARY_MARGIN, Math.min(MAP_WIDTH - BOUNDARY_MARGIN, projected.x));
      const y = Math.max(BOUNDARY_MARGIN, Math.min(MAP_HEIGHT - BOUNDARY_MARGIN, projected.y));
      
      return {
        id: logData.id,
        name: logData.name,
        mmsi: logData.mmsi,
        x: projected.x,
        y: projected.y,
        lat: logData.lat,
        lon: logData.lon,
        status: logData.status,
        heading: Math.random() * 360,
        speed: logData.speed,
        lastAnomaly: logData.status !== 'normal' ? new Date(Date.now() - Math.random() * 3600000) : null,
        trail: [],
        route: generateRoute(projected.x, projected.y),
        routeIndex: 0,
        vesselType: logData.type,
        loiteringDuration: logData.status === 'loitering' ? Math.floor(Math.random() * 120) + 30 : null, // minutes
        previousPoint: logData.status === 'spoofing' ? { x: projected.x - 50, y: projected.y - 30 } : null
      };
    });

    // Add a few more random vessels to fill the map with realistic lat/lon
    const additionalVessels = Array.from({ length: 5 }, (_, i) => {
      const vesselTypes = ['Cargo', 'Tanker', 'Fishing', 'Passenger', 'Tug'];
      const statuses = ['normal', 'loitering', 'spoofing'];
      const status = statuses[Math.floor(Math.random() * statuses.length)];
      
      // Generate random lat/lon within bounds
      const lat = 25.5 + Math.random() * 5;
      const lon = -97.5 + Math.random() * 15;
      const projected = project(lat, lon);
      
      return {
        id: 11 + i,
        name: `${vesselTypes[Math.floor(Math.random() * vesselTypes.length)]}-${String(11 + i).padStart(3, '0')}`,
        mmsi: 367000000 + Math.floor(Math.random() * 999999),
        x: projected.x,
        y: projected.y,
        lat: lat,
        lon: lon,
        status: status,
        heading: Math.random() * 360,
        speed: Math.random() * 25 + 5,
        lastAnomaly: status !== 'normal' ? new Date(Date.now() - Math.random() * 3600000) : null,
        trail: [],
        route: generateRoute(projected.x, projected.y),
        routeIndex: 0,
        vesselType: vesselTypes[Math.floor(Math.random() * vesselTypes.length)],
        loiteringDuration: status === 'loitering' ? Math.floor(Math.random() * 120) + 30 : null,
        previousPoint: status === 'spoofing' ? { x: projected.x - 50, y: projected.y - 30 } : null
      };
    });

    setVessels([...initialVessels, ...additionalVessels]);
  }, []);

  // Find nearest port for a vessel
  const findNearestPort = useCallback((vessel) => {
    if (!vessel?.lat || !vessel?.lon) return null;
    
    let nearest = null;
    let minDistance = Infinity;
    
    PORTS.forEach(port => {
      const distance = haversineNm(vessel.lat, vessel.lon, port.lat, port.lon);
      if (distance < minDistance) {
        minDistance = distance;
        nearest = { ...port, distanceNm: distance };
      }
    });
    
    return nearest ? {
      ...nearest,
      isInInfluence: nearest.distanceNm <= nearest.influenceNm
    } : null;
  }, []);

  // Helper function to get context label based on vessel status and port proximity
  const getContextLabel = (vesselStatus, distanceNm, influenceNm) => {
    if (!vesselStatus || typeof distanceNm !== 'number' || typeof influenceNm !== 'number') {
      return null;
    }
    
    // For loitering vessels, show influence zone context
    if (vesselStatus === 'loitering') {
      return distanceNm <= influenceNm ? 'Inside influence' : 'Outside influence';
    }
    
    // For normal (and other) vessels, show neutral context labels
    if (distanceNm > influenceNm) {
      return 'Open sea (in transit)';
    } else {
      return 'Near port traffic';
    }
  };

  // Get focused vessel context
  const focusedVesselContext = useMemo(() => {
    if (!highlightedVesselId || !focusMode) return null;
    const vessel = vessels.find(v => v.id === highlightedVesselId);
    if (!vessel) return null;
    
    const nearestPort = findNearestPort(vessel);
    return { vessel, nearestPort };
  }, [highlightedVesselId, focusMode, vessels, findNearestPort]);

  // Center map on highlighted vessel when it changes
  useEffect(() => {
    if (highlightedVesselId && highlightedVesselId !== prevHighlightedId.current && vessels.length > 0) {
      const vessel = vessels.find(v => v.id === highlightedVesselId);
      if (vessel && svgRef.current) {
        // Calculate center point of vessel in SVG coordinates
        const vesselCenterX = vessel.x;
        const vesselCenterY = vessel.y;
        
        // Get current viewBox (default is 0,0,800,600)
        const viewBoxWidth = 800;
        const viewBoxHeight = 600;
        
        const newX = vesselCenterX < viewBoxWidth / 2 ? 0 : 
                     vesselCenterX > 800 - viewBoxWidth / 2 ? 800 - viewBoxWidth : 
                     vesselCenterX - viewBoxWidth / 2;
        const newY = vesselCenterY < viewBoxHeight / 2 ? 0 : 
                     vesselCenterY > 600 - viewBoxHeight / 2 ? 600 - viewBoxHeight : 
                     vesselCenterY - viewBoxHeight / 2;
        
        // Smoothly transition to new viewBox
        setViewBox({
          x: Math.max(0, Math.min(800 - viewBoxWidth, newX)),
          y: Math.max(0, Math.min(600 - viewBoxHeight, newY)),
          width: viewBoxWidth,
          height: viewBoxHeight
        });
        
        // Enter focus mode
        setFocusMode(true);
        
        // Reset zoom to ensure vessel is visible
        setZoom(1);
        setViewBox({ x: 0, y: 0, width: 800, height: 600 });
        
        // Reset pan offset when centering on vessel
        setPanOffset({ x: 0, y: 0 });
        
        // Store the highlighted ID
        prevHighlightedId.current = highlightedVesselId;
      }
    } else if (!highlightedVesselId) {
      prevHighlightedId.current = null;
      setFocusMode(false);
    }
  }, [highlightedVesselId, vessels]);

  // ESC key handler to exit focus mode
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape' && focusMode) {
        setFocusMode(false);
        onVesselClick?.(null);
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [focusMode, onVesselClick]);

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
    // Only trigger vessel click if it wasn't a drag operation
    if (!hasMovedDuringDrag.current && vessel) {
    onVesselClick?.(vessel);
    }
  };

  const handleMouseMove = (e) => {
    // Handle drag/pan
    if (isDragging) {
      const rect = svgRef.current?.getBoundingClientRect();
      if (rect) {
        const deltaX = e.clientX - dragStart.x;
        const deltaY = e.clientY - dragStart.y;
        
        // Check if mouse moved enough to consider it a drag
        if (Math.abs(deltaX) > dragThreshold.current || Math.abs(deltaY) > dragThreshold.current) {
          hasMovedDuringDrag.current = true;
        }
        
        // Constrain panning within reasonable bounds (±50% of viewBox dimensions)
        const maxPanX = viewBox.width * 0.5;
        const maxPanY = viewBox.height * 0.5;
        
        // Convert screen delta to SVG coordinate delta (accounting for viewBox scale)
        const svgRect = svgRef.current?.getBoundingClientRect();
        if (svgRect) {
          const scaleX = viewBox.width / svgRect.width;
          const scaleY = viewBox.height / svgRect.height;
          
          const newPanX = Math.max(-maxPanX, Math.min(maxPanX, panOffset.x + deltaX * scaleX));
          const newPanY = Math.max(-maxPanY, Math.min(maxPanY, panOffset.y + deltaY * scaleY));
          
          setPanOffset({ x: newPanX, y: newPanY });
          setDragStart({ x: e.clientX, y: e.clientY });
        }
      }
    }
    
    // Handle tooltip positioning (only if not dragging)
    if (hoveredVessel && !isDragging) {
      const rect = svgRef.current?.getBoundingClientRect();
      if (rect) {
        setTooltipPosition({
          x: e.clientX - rect.left,
          y: e.clientY - rect.top
        });
      }
    }
  };

  const handleMouseDown = (e) => {
    // Don't start drag on interactive elements (vessels, controls, buttons)
    const target = e.target;
    if (target && (
      target.closest('[data-vessel-id]') ||
      target.closest('button') ||
      target.closest('[role="button"]') ||
      target.tagName === 'BUTTON'
    )) {
      return;
    }
    
    // Only start drag on left mouse button
    if (e.button === 0) {
      setIsDragging(true);
      hasMovedDuringDrag.current = false;
      setDragStart({ x: e.clientX, y: e.clientY });
    }
  };

  const handleMouseUp = (e) => {
    if (isDragging) {
      setIsDragging(false);
      // Reset drag start
      setDragStart({ x: 0, y: 0 });
      hasMovedDuringDrag.current = false;
    }
  };

  const handleMouseLeave = () => {
    if (isDragging) {
      setIsDragging(false);
      setDragStart({ x: 0, y: 0 });
      hasMovedDuringDrag.current = false;
    }
  };

  const handlePlayback = () => {
    setIsPlaying(!isPlaying);
  };

  const handleZoom = (direction) => {
    setZoom(prev => {
      const newZoom = Math.max(0.5, Math.min(3, prev + (direction === 'in' ? 0.2 : -0.2)));
      
      // Calculate current view center
      const currentCenterX = viewBox.x + viewBox.width / 2;
      const currentCenterY = viewBox.y + viewBox.height / 2;
      
      // Calculate new viewBox dimensions based on zoom
      const baseWidth = 800;
      const baseHeight = 600;
      const newWidth = baseWidth / newZoom;
      const newHeight = baseHeight / newZoom;
      
      // Keep center point, adjust viewBox
      const newX = Math.max(0, Math.min(800 - newWidth, currentCenterX - newWidth / 2));
      const newY = Math.max(0, Math.min(600 - newHeight, currentCenterY - newHeight / 2));
      
      setViewBox({
        x: newX,
        y: newY,
        width: newWidth,
        height: newHeight
      });
      
      return newZoom;
    });
  };

  const handleResetView = () => {
    setZoom(1);
    setViewBox({ x: 0, y: 0, width: 800, height: 600 });
    setPanOffset({ x: 0, y: 0 }); // Reset pan offset
    setPlaybackTime(100);
    setIsPlaying(false);
    setFocusMode(false);
    onVesselClick?.(null);
  };

  const handleClearFocus = () => {
    setFocusMode(false);
    onVesselClick?.(null);
  };

  // Panel management with mutual exclusivity
  const openPanel = (panelType) => {
    // Close all panels first
    setShowLayersPanel(false);
    setShowLegendPanel(false);
    setShowLiveViewPanel(false);
    
    // Open the requested panel
    if (panelType === 'layers') {
      setShowLayersPanel(true);
    } else if (panelType === 'legend') {
      setShowLegendPanel(true);
    } else if (panelType === 'liveView') {
      setShowLiveViewPanel(true);
    }
  };

  const closeAllPanels = () => {
    setShowLayersPanel(false);
    setShowLegendPanel(false);
    setShowLiveViewPanel(false);
  };

  // ESC key handler
  useEffect(() => {
    const handleEscKey = (event) => {
      if (event.key === 'Escape') {
        closeAllPanels();
      }
    };

    window.addEventListener('keydown', handleEscKey);
    return () => window.removeEventListener('keydown', handleEscKey);
  }, []);

  const zones = [
    { name: 'Restricted Zone Alpha', x: 150, y: 100, width: 120, height: 80, color: 'rgba(255, 0, 0, 0.2)' },
    { name: 'EEZ Boundary', x: 300, y: 200, width: 200, height: 150, color: 'rgba(255, 255, 0, 0.15)' },
    { name: 'Port Houston', x: 500, y: 350, width: 100, height: 60, color: 'rgba(0, 255, 0, 0.2)' }
  ];

  return (
    <div className="flex-1 p-4 md:p-6 relative">
      <div className="bg-slate-800/30 rounded-xl border border-cyan-500/30 h-full relative overflow-hidden">
        {/* Map Header - Collapsible */}
        <div className="absolute top-2 md:top-4 left-2 md:left-4 z-20">
          {showLiveViewPanel ? (
            <div className="bg-slate-900/80 backdrop-blur-sm rounded-lg p-2 md:p-3 border border-cyan-500/30 shadow-lg max-w-[200px] md:max-w-none">
              <div className="flex items-start justify-between mb-2">
                <h2 className="text-sm md:text-lg font-semibold text-cyan-400">Gulf of Mexico - Dataset View</h2>
                <button
                  onClick={closeAllPanels}
                  className="text-gray-400 hover:text-white transition-colors p-0.5 ml-2"
                  aria-label="Close"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
              <div className="text-xs text-gray-400 space-y-0.5 md:space-y-1">
                <div className="truncate">Lat: 25.5°N - 30.5°N</div>
                <div className="truncate">Lng: 97.5°W - 82.5°W</div>
                <div className="flex items-center space-x-1 mt-1 md:mt-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full" aria-hidden="true"></div>
                  <span>Historical AIS Playback (Marine Cadaster Dataset)</span>
                </div>
              </div>
            </div>
          ) : (
            <button
              onClick={() => openPanel('liveView')}
              className="bg-slate-900/80 backdrop-blur-sm rounded-full px-3 py-1.5 border border-cyan-500/30 shadow-lg hover:bg-slate-800/90 transition-all flex items-center space-x-2 text-xs md:text-sm text-cyan-400"
              aria-label="Show dataset view details"
              title="Latest available data from Marine Cadaster dataset"
            >
              <Info className="w-3 h-3 md:w-4 md:h-4" />
              <span>Dataset End</span>
            </button>
          )}
        </div>

        {/* Context Ribbon - Vessel Focus Info (appears next to map header in focus mode) */}
        {focusMode && focusedVesselContext && (
          <div className="absolute top-2 md:top-4 left-[220px] md:left-[240px] z-30 bg-slate-900/80 backdrop-blur-sm rounded-lg p-3 border border-cyan-500/50 shadow-xl w-[280px]">
            <div className="flex items-start justify-between mb-2">
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-cyan-400 mb-1">{focusedVesselContext.vessel.name}</h3>
                <div className="text-xs text-gray-300 font-mono mb-2">MMSI: {focusedVesselContext.vessel.mmsi}</div>
                <div className="flex items-center space-x-2 mb-2">
                  <span className="text-xs text-gray-400">Status:</span>
                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                    focusedVesselContext.vessel.status === 'normal' ? 'bg-green-600 text-white' :
                    focusedVesselContext.vessel.status === 'loitering' ? 'bg-yellow-400 text-black' :
                    'bg-red-600 text-white'
                  }`}>
                    {focusedVesselContext.vessel.status.toUpperCase()}
                  </span>
                </div>
              </div>
              <button
                onClick={handleClearFocus}
                className="text-gray-400 hover:text-red-400 transition-colors ml-2"
                aria-label="Clear focus"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            
            {focusedVesselContext.nearestPort && (
              <div className="pt-2 border-t border-slate-700 space-y-1.5">
                <div className="text-xs">
                  <span className="text-gray-400">Nearest Port: </span>
                  <span className="text-cyan-300 font-semibold">{focusedVesselContext.nearestPort.name}</span>
                  <span className="text-gray-300 ml-1">({focusedVesselContext.nearestPort.distanceNm.toFixed(1)} NM)</span>
                </div>
                {(() => {
                  const contextLabel = getContextLabel(
                    focusedVesselContext.vessel.status,
                    focusedVesselContext.nearestPort.distanceNm,
                    focusedVesselContext.nearestPort.influenceNm
                  );
                  if (!contextLabel) return null;
                  
                  const isLoitering = focusedVesselContext.vessel.status === 'loitering';
                  const isInsideInfluence = focusedVesselContext.nearestPort.isInInfluence;
                  
                  return (
                    <div className="text-xs">
                      <span className="text-gray-400">{isLoitering ? 'Zone context: ' : 'Context: '}</span>
                      <span className={
                        isLoitering 
                          ? (isInsideInfluence ? 'text-green-400' : 'text-gray-300')
                          : 'text-gray-300'
                      }>
                        {contextLabel}
                      </span>
                    </div>
                  );
                })()}
              </div>
            )}
            
            <div className="mt-2 pt-2 border-t border-slate-700 text-xs text-gray-400">
              Press ESC to exit focus mode
            </div>
          </div>
        )}

        {/* Right-side Dock Container */}
        <div className="absolute top-2 md:top-4 right-2 md:right-4 z-30 flex flex-col space-y-2">
          {/* Dock Buttons */}
          <div className="flex flex-col space-y-2">
            <button
              onClick={() => showLayersPanel ? closeAllPanels() : openPanel('layers')}
              className={`backdrop-blur-sm rounded-lg p-2 border shadow-lg hover:bg-slate-800/90 transition-all ${
                showLayersPanel 
                  ? 'bg-cyan-500/20 border-cyan-500/50' 
                  : 'bg-slate-900/80 border-cyan-500/30'
              }`}
              aria-label={showLayersPanel ? "Close layers panel" : "Open layers panel"}
              aria-expanded={showLayersPanel}
            >
              <Layers className={`w-4 h-4 md:w-5 md:h-5 transition-colors ${showLayersPanel ? 'text-cyan-400' : 'text-cyan-400/70'}`} />
            </button>

            <button
              onClick={() => showLegendPanel ? closeAllPanels() : openPanel('legend')}
              className={`backdrop-blur-sm rounded-lg p-2 border shadow-lg hover:bg-slate-800/90 transition-all ${
                showLegendPanel 
                  ? 'bg-cyan-500/20 border-cyan-500/50' 
                  : 'bg-slate-900/80 border-cyan-500/30'
              }`}
              aria-label={showLegendPanel ? "Close legend panel" : "Open legend panel"}
              aria-expanded={showLegendPanel}
            >
              <Menu className={`w-4 h-4 md:w-5 md:h-5 transition-colors ${showLegendPanel ? 'text-cyan-400' : 'text-cyan-400/70'}`} />
            </button>
          </div>

          {/* Layers Panel */}
          {showLayersPanel && (
            <div className="bg-slate-900/80 backdrop-blur-sm rounded-lg p-2.5 border border-cyan-500/30 shadow-xl w-[180px]">
              <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-slate-700/50">
                <h3 className="text-xs font-semibold text-cyan-400">Map Layers</h3>
                <button
                  onClick={closeAllPanels}
                  className="text-gray-400 hover:text-white transition-colors p-0.5"
                  aria-label="Close layers panel"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            <div className="space-y-1">
              <label className="flex items-center space-x-2 cursor-pointer py-0.5">
                <input
                  type="checkbox"
                  checked={layersVisible.ports}
                  onChange={(e) => {
                    e.stopPropagation();
                    setLayersVisible(prev => ({ ...prev, ports: e.target.checked }));
                  }}
                  className="w-3 h-3 rounded border-2 border-slate-600 bg-slate-800 text-cyan-500 focus:ring-1 focus:ring-cyan-500 cursor-pointer transition-all
                    checked:bg-cyan-500 checked:border-cyan-500"
                />
                <span className={`text-xs ${layersVisible.ports ? 'text-cyan-300' : 'text-gray-400'}`}>
                  Ports
                </span>
              </label>
              <label className="flex items-center space-x-2 cursor-pointer py-0.5">
                <input
                  type="checkbox"
                  checked={layersVisible.portInfluence}
                  onChange={(e) => {
                    e.stopPropagation();
                    setLayersVisible(prev => ({ ...prev, portInfluence: e.target.checked }));
                  }}
                  className="w-3 h-3 rounded border-2 border-slate-600 bg-slate-800 text-cyan-500 focus:ring-1 focus:ring-cyan-500 cursor-pointer transition-all
                    checked:bg-cyan-500 checked:border-cyan-500"
                />
                <span className={`text-xs ${layersVisible.portInfluence ? 'text-cyan-300' : 'text-gray-400'}`}>
                  Port Influence Zones
                </span>
              </label>
              <label className="flex items-center space-x-2 cursor-pointer py-0.5">
                <input
                  type="checkbox"
                  checked={layersVisible.eezBoundary}
                  onChange={(e) => {
                    e.stopPropagation();
                    setLayersVisible(prev => ({ ...prev, eezBoundary: e.target.checked }));
                  }}
                  className="w-3 h-3 rounded border-2 border-slate-600 bg-slate-800 text-cyan-500 focus:ring-1 focus:ring-cyan-500 cursor-pointer transition-all
                    checked:bg-cyan-500 checked:border-cyan-500"
                />
                <span className={`text-xs ${layersVisible.eezBoundary ? 'text-cyan-300' : 'text-gray-400'}`}>
                  EEZ Boundary
                </span>
              </label>
              <label className="flex items-center space-x-2 cursor-pointer py-0.5">
                <input
                  type="checkbox"
                  checked={layersVisible.restrictedAreas}
                  onChange={(e) => {
                    e.stopPropagation();
                    setLayersVisible(prev => ({ ...prev, restrictedAreas: e.target.checked }));
                  }}
                  className="w-3 h-3 rounded border-2 border-slate-600 bg-slate-800 text-cyan-500 focus:ring-1 focus:ring-cyan-500 cursor-pointer transition-all
                    checked:bg-cyan-500 checked:border-cyan-500"
                />
                <span className={`text-xs ${layersVisible.restrictedAreas ? 'text-cyan-300' : 'text-gray-400'}`}>
                  Restricted Areas
                </span>
              </label>
              <label className="flex items-center space-x-2 cursor-pointer py-0.5">
                <input
                  type="checkbox"
                  checked={layersVisible.evidenceOverlays}
                  onChange={(e) => {
                    e.stopPropagation();
                    setLayersVisible(prev => ({ ...prev, evidenceOverlays: e.target.checked }));
                  }}
                  className="w-3 h-3 rounded border-2 border-slate-600 bg-slate-800 text-cyan-500 focus:ring-1 focus:ring-cyan-500 cursor-pointer transition-all
                    checked:bg-cyan-500 checked:border-cyan-500"
                />
                <span className={`text-xs ${layersVisible.evidenceOverlays ? 'text-cyan-300' : 'text-gray-400'}`}>
                  Evidence Overlays
                </span>
              </label>
            </div>
            </div>
          )}

          {/* Legend Panel */}
          {showLegendPanel && (
            <div className="bg-slate-900/80 backdrop-blur-sm rounded-lg p-2 border border-cyan-500/30 shadow-lg w-[150px]">
              <div className="flex items-center justify-between mb-1.5 pb-1 border-b border-slate-700/50">
                <h3 className="text-xs font-semibold text-cyan-400">Legend</h3>
                <button
                  onClick={closeAllPanels}
                  className="text-gray-400 hover:text-white transition-colors p-0.5"
                  aria-label="Close legend panel"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
              <div className="space-y-1 mb-2">
                <div className="text-xs font-semibold text-gray-400 mb-1">Vessel Status</div>
                <div className="flex items-center space-x-1.5">
                  <div className="w-2 h-2 bg-cyan-400 rounded-full flex-shrink-0" aria-hidden="true"></div>
                  <span className="text-xs text-gray-300">Normal</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <div className="w-2 h-2 bg-orange-400 rounded-full flex-shrink-0" aria-hidden="true"></div>
                  <span className="text-xs text-gray-300">Loitering</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <div className="w-2 h-2 bg-red-400 rounded-full flex-shrink-0" aria-hidden="true"></div>
                  <span className="text-xs text-gray-300">Spoofing</span>
                </div>
              </div>
              <div className="space-y-1 pt-1.5 border-t border-slate-700/50">
                <div className="text-xs font-semibold text-gray-400 mb-1">Zones</div>
                <div className="flex items-center space-x-1.5">
                  <div className="w-2 h-1.5 bg-red-500/40 border border-red-500 flex-shrink-0" aria-hidden="true"></div>
                  <span className="text-xs text-gray-300">Restricted</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <div className="w-2 h-1.5 bg-yellow-500/30 border border-yellow-500 flex-shrink-0" aria-hidden="true"></div>
                  <span className="text-xs text-gray-300">EEZ Boundary</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <div className="w-2 h-1.5 bg-green-500/40 border border-green-500 flex-shrink-0" aria-hidden="true"></div>
                  <span className="text-xs text-gray-300">Port Area</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* SVG Map Container */}
        <svg 
          ref={svgRef} 
          className="w-full h-full transition-all duration-300 ease-in-out" 
          viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.width} ${viewBox.height}`}
          preserveAspectRatio="xMidYMid meet"
          aria-label="Maritime map showing vessel positions"
          style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseLeave}
          onTouchStart={(e) => {
            if (e.touches.length === 1) {
              const touch = e.touches[0];
              setIsDragging(true);
              hasMovedDuringDrag.current = false;
              setDragStart({ x: touch.clientX, y: touch.clientY });
              e.preventDefault();
            }
          }}
          onTouchMove={(e) => {
            if (isDragging && e.touches.length === 1) {
              const touch = e.touches[0];
              const rect = svgRef.current?.getBoundingClientRect();
              if (rect) {
                const deltaX = touch.clientX - dragStart.x;
                const deltaY = touch.clientY - dragStart.y;
                
                if (Math.abs(deltaX) > dragThreshold.current || Math.abs(deltaY) > dragThreshold.current) {
                  hasMovedDuringDrag.current = true;
                }
                
                const maxPanX = viewBox.width * 0.5;
                const maxPanY = viewBox.height * 0.5;
                
                const scaleX = viewBox.width / rect.width;
                const scaleY = viewBox.height / rect.height;
                
                const newPanX = Math.max(-maxPanX, Math.min(maxPanX, panOffset.x + deltaX * scaleX));
                const newPanY = Math.max(-maxPanY, Math.min(maxPanY, panOffset.y + deltaY * scaleY));
                
                setPanOffset({ x: newPanX, y: newPanY });
                setDragStart({ x: touch.clientX, y: touch.clientY });
              }
              e.preventDefault();
            }
          }}
          onTouchEnd={(e) => {
            if (isDragging) {
              setIsDragging(false);
              setDragStart({ x: 0, y: 0 });
              hasMovedDuringDrag.current = false;
            }
          }}
        >
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

            {/* Gulf mask for dimming outside bounds */}
            <mask id="gulfMask">
              <rect width="800" height="600" fill="black" />
              <rect x="50" y="50" width="700" height="500" fill="white" />
            </mask>
</defs>

          {/* Map content group with pan transform */}
          <g transform={`translate(${panOffset.x}, ${panOffset.y})`}>
          {/* Ocean background */}
          <rect width="800" height="600" fill="url(#oceanGradient)" />

          {/* Gulf of Mexico mask - dim area outside bounds */}
          <rect width="800" height="600" fill="rgba(0, 0, 0, 0.25)" mask="url(#gulfMask)" />

          {/* Subtle region labels */}
          <text x="200" y="100" textAnchor="middle" fill="rgba(200, 200, 200, 0.4)" fontSize="14" fontWeight="300" className="pointer-events-none">
            Texas
          </text>
          <text x="450" y="120" textAnchor="middle" fill="rgba(200, 200, 200, 0.4)" fontSize="14" fontWeight="300" className="pointer-events-none">
            Louisiana
          </text>
          <text x="650" y="150" textAnchor="middle" fill="rgba(200, 200, 200, 0.4)" fontSize="14" fontWeight="300" className="pointer-events-none">
            Florida
          </text>
          <text x="400" y="350" textAnchor="middle" fill="rgba(180, 200, 255, 0.5)" fontSize="16" fontWeight="300" className="pointer-events-none">
            Gulf of Mexico
          </text>

          {/* Zones - EEZ Boundary and Restricted Areas */}
          {layersVisible.eezBoundary && Array.isArray(zones) && zones.filter(z => z.name.includes('EEZ')).map((zone, index) => (
            <g key={`eez-${index}`}>
              <rect
                x={zone.x}
                y={zone.y}
                width={zone.width}
                height={zone.height}
                fill="none"
                stroke="rgba(255, 255, 0, 0.4)"
                strokeWidth="2"
                strokeDasharray="5,5"
              />
            </g>
          ))}
          {layersVisible.restrictedAreas && Array.isArray(zones) && zones.filter(z => z.name.includes('Restricted')).map((zone, index) => (
            <g key={`restricted-${index}`}>
              <rect
                x={zone.x}
                y={zone.y}
                width={zone.width}
                height={zone.height}
                fill="rgba(255, 0, 0, 0.2)"
                stroke="rgba(255, 0, 0, 0.6)"
                strokeWidth="2"
                strokeDasharray="5,5"
              />
              <text
                x={zone.x + zone.width / 2}
                y={zone.y + zone.height / 2}
                textAnchor="middle"
                dominantBaseline="middle"
                fill="rgba(255, 255, 255, 0.8)"
                fontSize="10"
                fontWeight="500"
                className="pointer-events-none"
              >
                {zone.name.replace('Zone ', '')}
              </text>
            </g>
          ))}

          {/* Port Influence Zones */}
          {layersVisible.portInfluence && Array.isArray(projectedPorts) && projectedPorts.map(port => {
            const isHighlighted = focusMode && focusedVesselContext?.nearestPort?.id === port.id;
            return (
              <g key={`port-zone-${port.id}`}>
                <circle
                  cx={port.x}
                  cy={port.y}
                  r={port.influenceRadius}
                  fill="none"
                  stroke={isHighlighted ? 'rgba(34, 211, 238, 0.4)' : 'rgba(16, 185, 129, 0.3)'}
                  strokeWidth={isHighlighted ? 2 : 1}
                  strokeDasharray={isHighlighted ? '0' : '5,5'}
                />
              </g>
            );
          })}

          {/* Port Markers */}
          {layersVisible.ports && Array.isArray(projectedPorts) && projectedPorts.map(port => {
            const isHighlighted = focusMode && focusedVesselContext?.nearestPort?.id === port.id;
            const labelOffset = port.labelAnchor === 'top' ? { x: 0, y: -25 } :
                              port.labelAnchor === 'bottom' ? { x: 0, y: 25 } :
                              port.labelAnchor === 'left' ? { x: -60, y: 0 } :
                              { x: 60, y: 0 };
            
            return (
              <g key={`port-${port.id}`}>
                <circle
                  cx={port.x}
                  cy={port.y}
                  r={isHighlighted ? 8 : 6}
                  fill={isHighlighted ? '#22d3ee' : '#10b981'}
                  stroke="white"
                  strokeWidth={isHighlighted ? 2 : 1}
                  opacity={isHighlighted ? 1 : 0.9}
                />
                <text
                  x={port.x + labelOffset.x}
                  y={port.y + labelOffset.y}
                  textAnchor={port.labelAnchor === 'left' ? 'end' : port.labelAnchor === 'right' ? 'start' : 'middle'}
                  dominantBaseline={port.labelAnchor === 'top' ? 'baseline' : port.labelAnchor === 'bottom' ? 'hanging' : 'middle'}
                  fill={isHighlighted ? '#22d3ee' : '#94a3b8'}
                  fontSize="10"
                  fontWeight={isHighlighted ? 'bold' : 'normal'}
                  className="pointer-events-none"
                >
                  {port.name}
                </text>
              </g>
            );
          })}


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

          {/* Evidence Overlays - Loitering circles */}
          {(layersVisible.evidenceOverlays || focusMode) && Array.isArray(vessels) && vessels.filter(v => v.status === 'loitering' && ((focusMode && v.id === highlightedVesselId) || layersVisible.evidenceOverlays)).map(vessel => (
            <g key={`loitering-${vessel.id}`}>
              <circle
                cx={vessel.x}
                cy={vessel.y}
                r={nmToPixels(2)}
                fill="none"
                stroke="#FF8C00"
                strokeWidth={focusMode && vessel.id === highlightedVesselId ? 2 : 1}
                strokeDasharray="4,4"
                opacity={focusMode && vessel.id === highlightedVesselId ? 0.8 : 0.4}
              />
              {(focusMode && vessel.id === highlightedVesselId) && (
                <text
                  x={vessel.x}
                  y={vessel.y + nmToPixels(2) + 15}
                  textAnchor="middle"
                  fill="#FF8C00"
                  fontSize="9"
                  fontWeight="bold"
                  className="pointer-events-none"
                >
                  Loitering: {vessel.loiteringDuration || '45'} min
                </text>
              )}
            </g>
          ))}

          {/* Evidence Overlays - Spoofing teleport lines */}
          {(layersVisible.evidenceOverlays || focusMode) && Array.isArray(vessels) && vessels.filter(v => v.status === 'spoofing' && v.previousPoint && ((focusMode && v.id === highlightedVesselId) || layersVisible.evidenceOverlays)).map(vessel => (
            <g key={`spoofing-${vessel.id}`}>
              <line
                x1={vessel.previousPoint.x}
                y1={vessel.previousPoint.y}
                x2={vessel.x}
                y2={vessel.y}
                stroke="#FF4444"
                strokeWidth={focusMode && vessel.id === highlightedVesselId ? 2 : 1}
                strokeDasharray="3,3"
                opacity={focusMode && vessel.id === highlightedVesselId ? 0.9 : 0.5}
              />
              {(focusMode && vessel.id === highlightedVesselId) && (
                <text
                  x={(vessel.previousPoint.x + vessel.x) / 2}
                  y={(vessel.previousPoint.y + vessel.y) / 2 - 10}
                  textAnchor="middle"
                  fill="#FF4444"
                  fontSize="9"
                  fontWeight="bold"
                  className="pointer-events-none"
                >
                  Teleport / Inconsistent speed
                </text>
              )}
            </g>
          ))}

          {/* Vessel trails with fade effect */}
          {Array.isArray(vessels) && vessels.map(vessel => {
            const isFocused = focusMode && vessel.id === highlightedVesselId;
            const isDimmed = focusMode && !isFocused;
            const isHighlighted = highlightedVesselId === vessel.id;
            
            // Determine if we should show anomaly trail (orange/yellow) vs normal trail (blue/white)
            const showAnomalyTrail = vessel.status === 'loitering' && (
              isHighlighted || 
              layersVisible.evidenceOverlays
            );
            
            // Normal vessels always show blue/white trails
            // Loitering vessels show orange/yellow only when selected or evidence overlays ON
            const trailColor = showAnomalyTrail 
              ? getVesselColor(vessel.status) // Orange for loitering anomaly
              : '#00D4FF'; // Blue/cyan for normal trails
            
            return (
              <g key={`trail-${vessel.id}`} opacity={isDimmed ? 0.2 : 1}>
              {vessel.trail.map((point, index) => {
                const age = Date.now() - point.timestamp;
                const maxAge = 600000; // 10 minutes
                  const baseOpacity = Math.max(0, 1 - (age / maxAge)) * 0.6;
                  
                  // Anomaly trails are thinner and more transparent
                  const trailRadius = showAnomalyTrail 
                    ? (1.5 * baseOpacity + 0.3) // Thinner for anomaly trails
                    : (2 * baseOpacity + 0.5); // Normal thickness
                  
                  const trailOpacity = showAnomalyTrail 
                    ? baseOpacity * 0.5 // More transparent for anomaly trails
                    : baseOpacity; // Normal opacity
                
                return (
                  <circle
                    key={`trail-point-${vessel.id}-${index}`}
                    cx={point.x}
                    cy={point.y}
                      r={trailRadius}
                      fill={trailColor}
                      opacity={trailOpacity}
                  />
                );
              })}
            </g>
            );
          })}

          {/* Vessels with enhanced graphics */}
          {Array.isArray(vessels) && vessels.map(vessel => {
            const isHighlighted = highlightedVesselId === vessel.id;
            const isFocused = focusMode && vessel.id === highlightedVesselId;
            const isDimmed = focusMode && !isFocused;
            
            return (
              <g 
                key={vessel.id} 
                data-vessel-id={vessel.id}
                transform={`translate(${vessel.x}, ${vessel.y}) rotate(${vessel.heading})`}
                style={{ cursor: 'pointer', opacity: isDimmed ? 0.2 : 1 }}
                className={isHighlighted ? "animate-pulse" : ""}
                onClick={() => handleVesselClick(vessel)}
                onMouseEnter={(e) => {
                  setHoveredVessel(vessel);
                  const rect = svgRef.current?.getBoundingClientRect();
                  if (rect) {
                    setTooltipPosition({
                      x: e.clientX - rect.left,
                      y: e.clientY - rect.top
                    });
                  }
                }}
                onMouseLeave={() => setHoveredVessel(null)}
                onMouseMove={(e) => {
                  const rect = svgRef.current?.getBoundingClientRect();
                  if (rect) {
                    setTooltipPosition({
                      x: e.clientX - rect.left,
                      y: e.clientY - rect.top
                    });
                  }
                }}
                role="button"
                tabIndex={0}
                aria-label={`Vessel ${vessel.name}, Status: ${vessel.status}`}
              >
                {/* Highlight ring for selected vessel */}
                {isHighlighted && (
                  <>
                    <circle
                      cx="0"
                      cy="0"
                      r="35"
                      fill="none"
                      stroke="rgb(34, 211, 238)"
                      strokeWidth="4"
                      strokeDasharray="8,4"
                      opacity="0.6"
                      className="animate-ping"
                    />
                    <circle
                      cx="0"
                      cy="0"
                      r="30"
                      fill="none"
                      stroke="rgb(34, 211, 238)"
                      strokeWidth="3"
                      opacity="1"
                    />
                  </>
                )}
                <use 
                  href="#vesselShape" 
                  fill={getVesselColor(vessel.status)}
                  className={getStatusGlow(vessel.status, isHighlighted)}
                  transform={isHighlighted ? 'scale(1.8)' : 'scale(1)'}
                  style={{ transition: 'transform 0.3s ease' }}
                />
                
                <text
                  x={isHighlighted ? "20" : "16"}
                  y={isHighlighted ? "-6" : "-2"}
                  fill={isHighlighted ? "rgb(34, 211, 238)" : getVesselColor(vessel.status)}
                  fontSize={isHighlighted ? "11" : "9"}
                  dominantBaseline="middle"
                  className="font-mono font-semibold"
                  style={{ 
                    textShadow: isHighlighted ? '0 0 10px rgba(34, 211, 238, 0.8)' : 'none',
                    transition: 'all 0.3s ease'
                  }}
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
          </g>
          {/* End of map content group */}

        </svg>

        {/* Hover Tooltip with better positioning */}
        {hoveredVessel && (
          <div 
            className="absolute z-30 bg-slate-900/95 backdrop-blur-sm border border-cyan-500/50 rounded-lg p-3 pointer-events-none shadow-xl min-w-[200px] max-w-[250px]"
            style={{
              left: `${tooltipPosition.x + 15}px`,
              top: `${tooltipPosition.y - 10}px`,
              transform: tooltipPosition.x > 600 ? 'translateX(-100%)' : 'none'
            }}
            role="tooltip"
            aria-live="polite"
          >
            <div className="text-cyan-400 font-semibold text-sm mb-2">{hoveredVessel.name}</div>
            <div className="text-xs text-gray-300 space-y-1">
              <div className="flex justify-between">
                <span className="text-gray-400">MMSI:</span>
                <span className="font-mono text-white">{hoveredVessel.mmsi}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Speed:</span>
                <span className="font-mono text-white">{hoveredVessel.speed.toFixed(1)} kts</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Heading:</span>
                <span className="font-mono text-white">{Math.round(hoveredVessel.heading)}°</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Type:</span>
                <span className="font-mono text-white">{hoveredVessel.vesselType}</span>
              </div>
              {hoveredVessel.lastAnomaly && (
                <div className="flex justify-between pt-1 border-t border-slate-600">
                  <span className="text-orange-400">Last Alert:</span>
                  <span className="text-orange-400 font-mono">
                    {hoveredVessel.lastAnomaly.toLocaleTimeString()}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Playback Controls */}
        <div className="absolute bottom-2 md:bottom-4 left-2 md:left-4 right-2 md:right-4 z-20 bg-slate-900/90 backdrop-blur-sm rounded-lg p-2 md:p-3 border border-cyan-500/30 shadow-lg">
          <div className="flex flex-col md:flex-row items-stretch md:items-center gap-2 md:gap-4">
            <button
              onClick={handlePlayback}
              aria-label={isPlaying ? "Pause playback" : "Play playback"}
              title="Replay historical vessel movements within selected time range"
              className="flex items-center justify-center space-x-2 px-3 py-2 bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-400 rounded-lg transition-all border border-cyan-500/30 focus:outline-none focus:ring-2 focus:ring-cyan-400 focus:ring-offset-2 focus:ring-offset-slate-900"
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              <span className="text-xs md:text-sm">{isPlaying ? 'Pause' : 'Play'}</span>
            </button>

            <div className="flex items-center space-x-2 text-xs md:text-sm flex-wrap">
              <span className="text-gray-400 whitespace-nowrap">Range:</span>
              {['24h', '7d', '30d'].map((range) => (
                <button
                  key={range}
                  onClick={() => setPlaybackRange(range)}
                  aria-label={`Set playback range to ${range}`}
                  className={`px-2 py-1 rounded text-xs transition-all border focus:outline-none focus:ring-2 focus:ring-cyan-400 focus:ring-offset-2 focus:ring-offset-slate-900 ${
                    playbackRange === range
                      ? 'bg-cyan-600/30 text-cyan-400 border-cyan-500/50'
                      : 'text-gray-400 hover:text-cyan-400 border-transparent hover:border-cyan-500/30'
                  }`}
                >
                  {range}
                </button>
              ))}
            </div>

            <div className="flex-1 min-w-0">
              <input
                type="range"
                min="0"
                max="100"
                value={playbackTime}
                onChange={(e) => setPlaybackTime(parseInt(e.target.value))}
                aria-label="Playback timeline (rightmost position = latest timestamp in dataset)"
                title="Rightmost position = latest timestamp in dataset"
                className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
                style={{
                  background: `linear-gradient(to right, rgb(6, 182, 212) 0%, rgb(6, 182, 212) ${playbackTime}%, rgb(51, 65, 85) ${playbackTime}%, rgb(51, 65, 85) 100%)`
                }}
              />
            </div>

            <div className="text-xs text-gray-400 min-w-fit text-center md:text-left">
              {playbackTime === 100 ? 'Latest' : `${playbackTime}% Complete`}
            </div>
          </div>
        </div>

        {/* Map Controls */}
        <div className="absolute bottom-16 md:bottom-20 left-2 md:left-4 z-20 flex flex-col space-y-2">
          <button 
            onClick={() => handleZoom('in')}
            aria-label="Zoom in"
            className="w-10 h-10 bg-slate-800/90 hover:bg-slate-700/90 border border-cyan-500/30 rounded-lg flex items-center justify-center text-cyan-400 transition-all shadow-lg focus:outline-none focus:ring-2 focus:ring-cyan-400 focus:ring-offset-2 focus:ring-offset-slate-900"
          >
            <ZoomIn className="w-5 h-5" aria-hidden="true" />
          </button>
          <button 
            onClick={() => handleZoom('out')}
            aria-label="Zoom out"
            className="w-10 h-10 bg-slate-800/90 hover:bg-slate-700/90 border border-cyan-500/30 rounded-lg flex items-center justify-center text-cyan-400 transition-all shadow-lg focus:outline-none focus:ring-2 focus:ring-cyan-400 focus:ring-offset-2 focus:ring-offset-slate-900"
          >
            <ZoomOut className="w-5 h-5" aria-hidden="true" />
          </button>
          <button 
            onClick={handleResetView}
            aria-label="Reset view"
            className="w-10 h-10 bg-slate-800/90 hover:bg-slate-700/90 border border-cyan-500/30 rounded-lg flex items-center justify-center text-cyan-400 transition-all shadow-lg focus:outline-none focus:ring-2 focus:ring-cyan-400 focus:ring-offset-2 focus:ring-offset-slate-900"
          >
            <RotateCcw className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default MapView;
