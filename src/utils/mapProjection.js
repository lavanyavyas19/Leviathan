// Map projection utilities for Gulf of Mexico
// Bounds: lat 25.5–30.5, lon -97.5–-82.5

const MAP_WIDTH = 800;
const MAP_HEIGHT = 600;
const BOUNDARY_MARGIN = 50;

// Latitude/Longitude bounds
const MIN_LAT = 25.5;
const MAX_LAT = 30.5;
const MIN_LON = -97.5;
const MAX_LON = -82.5;

/**
 * Project lat/lon coordinates to map x/y coordinates (equirectangular projection)
 * @param {number} lat - Latitude
 * @param {number} lon - Longitude
 * @returns {{x: number, y: number}} - Map coordinates
 */
export const project = (lat, lon) => {
  // Normalize to 0-1 range
  const normalizedX = (lon - MIN_LON) / (MAX_LON - MIN_LON);
  const normalizedY = 1 - (lat - MIN_LAT) / (MAX_LAT - MIN_LAT); // Invert Y axis
  
  // Scale to map dimensions
  const x = normalizedX * (MAP_WIDTH - BOUNDARY_MARGIN * 2) + BOUNDARY_MARGIN;
  const y = normalizedY * (MAP_HEIGHT - BOUNDARY_MARGIN * 2) + BOUNDARY_MARGIN;
  
  // Ensure within bounds
  return {
    x: Math.max(BOUNDARY_MARGIN, Math.min(MAP_WIDTH - BOUNDARY_MARGIN, x)),
    y: Math.max(BOUNDARY_MARGIN, Math.min(MAP_HEIGHT - BOUNDARY_MARGIN, y))
  };
};

/**
 * Calculate Haversine distance between two lat/lon points in nautical miles
 * @param {number} lat1 - First point latitude
 * @param {number} lon1 - First point longitude
 * @param {number} lat2 - Second point latitude
 * @param {number} lon2 - Second point longitude
 * @returns {number} - Distance in nautical miles
 */
export const haversineNm = (lat1, lon1, lat2, lon2) => {
  const R = 3440.065; // Earth radius in nautical miles
  
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  
  const a = 
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  
  return R * c;
};

/**
 * Convert nautical miles to pixels for map display
 * @param {number} nm - Distance in nautical miles
 * @returns {number} - Distance in pixels (approximate)
 */
export const nmToPixels = (nm) => {
  // Approximate conversion: at mean latitude (~28°N), 1 degree ≈ 60 NM
  // Map width represents ~15 degrees longitude ≈ 900 NM
  // So 1 NM ≈ (MAP_WIDTH - 2*BOUNDARY_MARGIN) / 900 pixels
  const mapWidthNm = 900; // Approximate width in NM
  const availableWidth = MAP_WIDTH - BOUNDARY_MARGIN * 2;
  
  return (nm / mapWidthNm) * availableWidth;
};

// Export constants if needed elsewhere
export { MAP_WIDTH, MAP_HEIGHT, BOUNDARY_MARGIN, MIN_LAT, MAX_LAT, MIN_LON, MAX_LON };
