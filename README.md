# LEVIATHAN 🚢

**Marine Vessel Tracking & Anomaly Detection System**

A comprehensive web application for visualizing and analyzing historical AIS (Automatic Identification System) vessel data in the Gulf of Mexico. Leviathan provides real-time visualization, anomaly detection (loitering and spoofing), and interactive analytics for marine traffic monitoring.

---

## 🌟 Features

### Core Functionality

- **Interactive Map Visualization**
  - SVG-based map of the Gulf of Mexico region
  - Real-time vessel position tracking with playback controls
  - Zoom, pan, and drag interactions
  - Port locations with influence zones
  - Vessel trails with color-coded status indicators

- **Anomaly Detection**
  - **Loitering Detection**: Identifies vessels exhibiting suspicious loitering behavior near ports
  - **Spoofing Detection**: Detects potential AIS signal spoofing or manipulation
  - ML-powered detection using pre-trained models (scikit-learn)

- **Data Visualization**
  - Anomaly Detection Trends chart with time-series analysis
  - Normalized metrics (anomalies per 100 vessels)
  - Baseline comparison with reference lines
  - Auto-generated insights summary
  - Interactive chart points for filtering vessels

- **Vessel Management**
  - Comprehensive vessel logs table with filtering
  - Vessel details modal with AIS information
  - "View on Map" integration for quick navigation
  - Status-based categorization (Normal, Loitering, Spoofing)

- **User Interface**
  - Collapsible panels (Map Layers, Legend, Dataset View)
  - Mutual exclusivity for expanded panels
  - Responsive design with Tailwind CSS
  - Dark theme optimized for maritime operations
  - Keyboard shortcuts (ESC to close panels)

### Map Features

- **Layers Panel**: Toggle visibility of ports, port influence zones, EEZ boundaries, restricted areas, and evidence overlays
- **Legend Panel**: Clear visualization of vessel status, zones, and map elements
- **Dataset View Panel**: Playback controls and timeline information
- **Evidence Overlays**: Yellow/orange trails for loitering vessels (shown only when vessel is selected or layer is active)
- **Context Labels**: Intelligent context display (Inside/Outside influence for loitering, Open sea/Near port traffic for normal vessels)

---

## 🛠️ Tech Stack

### Frontend
- **React 18** - UI framework
- **Vite** - Build tool and development server
- **Tailwind CSS** - Utility-first CSS framework
- **Recharts** - Charting library for data visualization
- **Lucide React** - Icon library
- **PapaParse** - CSV parsing

### Backend
- **FastAPI** - Python web framework
- **scikit-learn** - Machine learning models
- **Pandas** - Data processing
- **NumPy** - Numerical computing
- **Uvicorn** - ASGI server
- **Geopy** - Geospatial calculations

---

## 📋 Prerequisites

- **Node.js** (v16 or higher)
- **Python** (v3.8 or higher)
- **pnpm** (package manager) or npm
- **pip** (Python package installer)

---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Leviathan
```

### 2. Frontend Setup

```bash
# Install dependencies
pnpm install
# or
npm install
```

### 3. Backend Setup

```bash
# Navigate to backend directory
cd leviathan-backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
.\venv\Scripts\Activate.ps1

# Install Python dependencies
pip install -r requirements.txt
```

### 4. Train ML Models (Optional)

If you need to retrain the anomaly detection models:

```bash
cd leviathan-backend
python train_loitering_model.py
python train_spoofing_model.py
```

The trained models will be saved in `leviathan-backend/app/ml/`:
- `loitering_model.pkl`
- `spoofing_model.pkl`

---

## 🎮 Usage

### Start Development Server

1. **Start Backend** (from `leviathan-backend/` directory):

```bash
uvicorn entry:app --reload
```

Backend will run on `http://localhost:8000`

2. **Start Frontend** (from root directory):

```bash
pnpm run dev
# or
npm run dev
```

Frontend will run on `http://localhost:5173`

### Build for Production

```bash
# Build frontend
pnpm run build
# or
npm run build

# Preview production build
pnpm run preview
```

---

## 📁 Project Structure

```
Leviathan/
├── src/
│   ├── components/
│   │   ├── Dashboard.jsx          # Main dashboard container
│   │   ├── MapView.jsx            # Interactive map component
│   │   ├── BottomChart.jsx        # Anomaly detection trends chart
│   │   ├── VesselLogs.jsx         # Vessel logs table
│   │   ├── RightPanel.jsx         # Alerts and system status
│   │   ├── Sidebar.jsx            # Navigation sidebar
│   │   └── LoginPage.jsx          # Authentication page
│   ├── utils/
│   │   └── mapProjection.js       # Map projection utilities
│   ├── App.jsx                    # Root component
│   └── main.jsx                   # Entry point
├── leviathan-backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py          # Configuration settings
│   │   │   ├── ingestion_engine.py # Data ingestion pipeline
│   │   │   └── preprocessing.py   # Data preprocessing
│   │   ├── ml/
│   │   │   ├── loitering_model.pkl
│   │   │   └── spoofing_model.pkl
│   │   └── routes/
│   │       ├── ingestion.py       # Data upload endpoints
│   │       ├── loitering.py       # Loitering detection API
│   │       └── spoofing.py        # Spoofing detection API
│   ├── data/
│   │   └── processed/             # Processed AIS data
│   ├── entry.py                   # FastAPI application entry
│   ├── train_loitering_model.py   # Model training script
│   └── train_spoofing_model.py    # Model training script
├── data/                          # Sample AIS datasets
├── public/                        # Static assets
└── README.md                      # This file
```

---

## 🗺️ Map Configuration

The map covers the Gulf of Mexico region with the following bounds:
- **Latitude**: 25.5°N to 30.5°N
- **Longitude**: 97.5°W to 82.5°W

### Ports Monitored

- Port of Houston (29.73°N, 95.27°W) - 20 NM influence
- Port of New Orleans (29.95°N, 90.07°W) - 18 NM influence
- Port of Corpus Christi (27.80°N, 97.40°W) - 18 NM influence
- Port of Tampa Bay (27.95°N, 82.45°W) - 16 NM influence
- Port of Mobile (30.70°N, 88.04°W) - 14 NM influence

---

## 🎨 UI Components

### Map View
- **Zoom Controls**: Zoom in/out buttons and scroll support
- **Pan/Drag**: Click and drag to pan the map
- **Playback Controls**: Play/pause, timeline slider, speed control
- **Layers Panel**: Toggle map layers (ports, zones, boundaries)
- **Legend Panel**: Visual guide for vessel status and zones
- **Dataset View Panel**: Playback information and controls

### Anomaly Reports (Bottom Chart)
- Time-series visualization of anomaly trends
- Normalized metrics toggle
- Baseline reference line
- Clickable chart points for vessel filtering
- Auto-generated insights summary

### Vessel Logs
- Sortable table with vessel information
- Filter by status, type, or time range
- Modal view with detailed vessel information
- "View on Map" button for quick navigation

### Right Panel
- Live alerts display
- System status indicators
- Collapsible panel design

---

## 🔧 Configuration

### Backend Configuration

Edit `leviathan-backend/app/core/config.py` to customize:
- Server host and port
- Database URL
- Data and models directory paths
- Environment variables via `.env` file

### Frontend Configuration

Key constants can be modified in:
- `src/utils/mapProjection.js` - Map bounds and dimensions
- `src/components/MapView.jsx` - Port configurations, UI settings

---

## 📊 Data Format

### AIS Data Structure

The system expects CSV files with the following columns:
- `mmsi` - Maritime Mobile Service Identity
- `lat` - Latitude
- `lon` - Longitude
- `speed` - Vessel speed (knots)
- `heading` - Vessel heading (degrees)
- `timestamp` - Timestamp of the AIS message
- Additional vessel metadata (type, name, etc.)

### API Endpoints

- `GET /` - Health check
- `POST /api/upload` - Upload AIS data CSV file
- `POST /api/loitering/detect` - Detect loitering anomalies
- `POST /api/spoofing/detect` - Detect spoofing anomalies

---

## 🐛 Troubleshooting

### Common Issues

1. **Blank page on localhost**
   - Ensure `mapProjection.js` exports all required functions
   - Check browser console for import errors

2. **Backend connection errors**
   - Verify backend is running on port 8000
   - Check CORS configuration in `entry.py`

3. **ML model errors**
   - Ensure model files exist in `leviathan-backend/app/ml/`
   - Retrain models if missing: `python train_*.py`

4. **Map not displaying**
   - Check browser console for SVG rendering errors
   - Verify vessel data is loaded correctly

---

## 🔐 Security Notes

- This application is designed for internal/demo use
- Implement proper authentication for production
- Secure API endpoints with rate limiting
- Validate and sanitize all user inputs
- Use HTTPS in production environments

---

## 📝 Development Notes

### Key Features Implemented

- ✅ Interactive SVG map with zoom, pan, and drag
- ✅ Vessel playback with timeline controls
- ✅ Anomaly detection visualization
- ✅ Collapsible UI panels with mutual exclusivity
- ✅ Evidence overlays for loitering vessels
- ✅ Context-aware vessel status labels
- ✅ Historical data semantics (not live streaming)
- ✅ Normalized metrics and baseline comparison
- ✅ Auto-generated insights summary
- ✅ Clickable chart points for filtering

### Performance Optimizations

- React memoization (`useMemo`, `useCallback`)
- Efficient SVG rendering
- Conditional rendering of overlays
- Optimized data processing

---

## 📄 License

[Add your license information here]

---

## 👥 Contributors

[Add contributor information here]

---

## 🔗 Resources

- [Recharts Documentation](https://recharts.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Tailwind CSS Documentation](https://tailwindcss.com/)

---

## 📧 Contact

[Add contact information here]

---

**Note**: This system operates on historical AIS datasets (Marine Cadaster) and does not stream live data. All playback functionality replays historical vessel movements within the selected time range.
