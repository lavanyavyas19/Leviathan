# Leviathan Project Structure

## Complete Directory Tree

```
Leviathan-main/
│
├── 📄 Configuration Files
│   ├── package.json                    # Frontend dependencies & scripts
│   ├── package-lock.json               # NPM lock file
│   ├── pnpm-lock.yaml                  # PNPM lock file
│   ├── vite.config.js                  # Vite build configuration
│   ├── tailwind.config.js              # Tailwind CSS configuration
│   ├── postcss.config.js               # PostCSS configuration
│   ├── eslint.config.js                # ESLint configuration
│   ├── index.html                      # HTML entry point
│   ├── amplifyconfiguration.json       # AWS Amplify configuration
│   ├── template_config.json            # Template configuration
│   ├── README.md                       # Project documentation
│   └── RECENT_CHANGES_AND_RECOMMENDATIONS.md
│
├── 📁 amplify/                         # AWS Amplify Backend Configuration
│   ├── cli.json                        # Amplify CLI configuration
│   ├── team-provider-info.json         # Team provider information
│   ├── .config/                        # Local Amplify configuration
│   │   ├── local-aws-info.json
│   │   ├── local-env-info.json
│   │   └── project-config.json
│   ├── #current-cloud-backend/         # Current cloud backend state
│   │   ├── amplify-meta.json
│   │   ├── backend-config.json
│   │   ├── tags.json
│   │   ├── auth/                       # Authentication resources
│   │   │   └── leviathandf73a36c/
│   │   │       ├── cli-inputs.json
│   │   │       └── build/
│   │   ├── storage/                    # Storage resources
│   │   │   └── leviathanstorage/
│   │   │       ├── cli-inputs.json
│   │   │       └── build/
│   │   └── awscloudformation/          # CloudFormation templates
│   │       └── build/
│   └── backend/                        # Local backend state
│       ├── amplify-meta.json
│       ├── backend-config.json
│       ├── tags.json
│       ├── types/
│       │   └── amplify-dependent-resources-ref.d.ts
│       ├── auth/
│       │   └── leviathandf73a36c/
│       ├── storage/
│       │   └── leviathanstorage/
│       └── awscloudformation/
│
├── 📁 src/                             # Frontend Source Code
│   ├── main.jsx                        # React entry point
│   ├── App.jsx                         # Root React component
│   ├── index.css                       # Global styles
│   ├── amplifyconfiguration.json       # Amplify config (duplicate)
│   ├── aws-exports.js                  # AWS exports
│   │
│   ├── 📁 components/                  # React Components
│   │   ├── Dashboard.jsx               # Main dashboard container
│   │   ├── MapView.jsx                 # Interactive map visualization
│   │   ├── BottomChart.jsx             # Anomaly detection trends chart
│   │   ├── VesselLogs.jsx              # Vessel logs table component
│   │   ├── RightPanel.jsx              # Alerts and system status panel
│   │   ├── Sidebar.jsx                 # Navigation sidebar
│   │   └── LoginPage.jsx               # Authentication page
│   │
│   └── 📁 utils/                       # Utility Functions
│       ├── api.js                      # API client functions
│       └── mapProjection.js            # Map projection utilities
│
├── 📁 leviathan-backend/               # Python Backend (FastAPI)
│   ├── entry.py                        # FastAPI application entry point
│   ├── requirements.txt                # Python dependencies
│   ├── .env                            # Environment variables
│   ├── ais_data.csv                    # Sample AIS data
│   │
│   ├── 📁 app/                         # Main application package
│   │   ├── __init__.py
│   │   │
│   │   ├── 📁 core/                    # Core functionality modules
│   │   │   ├── __init__.py
│   │   │   ├── config.py               # Configuration settings
│   │   │   ├── anomaly_detection.py    # Anomaly detection logic
│   │   │   ├── dataset_registry.py     # Dataset management
│   │   │   ├── ingestion_engine.py     # Data ingestion pipeline
│   │   │   ├── job_store.py            # Job storage management
│   │   │   └── preprocessing.py        # Data preprocessing
│   │   │
│   │   ├── 📁 ml/                      # Machine Learning Models
│   │   │   ├── loitering_model.pkl     # Trained loitering detection model
│   │   │   ├── spoofing_model.pkl      # Trained spoofing detection model
│   │   │   └── spoofing_events.pkl     # Spoofing events data
│   │   │
│   │   ├── 📁 routes/                  # API Route Handlers
│   │   │   ├── __init__.py
│   │   │   ├── dataset.py              # Dataset management endpoints
│   │   │   ├── ingestion.py            # Data ingestion endpoints
│   │   │   ├── job.py                  # Job management endpoints
│   │   │   ├── loitering.py            # Loitering detection API
│   │   │   └── spoofing.py             # Spoofing detection API
│   │   │
│   │   └── 📁 utils/                   # Backend Utilities
│   │       └── s3_upload.py             # S3 upload functionality
│   │
│   ├── 📁 data/                        # Data Storage
│   │   ├── AIS_2022_01_01.csv          # Historical AIS data
│   │   ├── AIS_2022_01_02.csv
│   │   ├── ais_data.csv
│   │   ├── ais_15_days_training.parquet # Training data
│   │   ├── cleaned_ais_compressed_24_01_01.csv
│   │   ├── compressed_ais_data.csv
│   │   ├── lavanya_credentials.csv
│   │   ├── 7c8f8297-6a11-487b-9d45-97c7aa1d8eeb_ais_injected_labeled.csv
│   │   ├── [multiple job UUID CSV files]
│   │   │
│   │   ├── 📁 jobs/                    # Job Results Storage
│   │   │   └── [UUID directories]/     # Individual job results
│   │   │       ├── loitering_events.pkl
│   │   │       └── spoofing_events.pkl
│   │   │
│   │   └── 📁 processed/               # Processed data cache
│   │
│   ├── 📁 routes/                      # Legacy routes (if any)
│   │
│   ├── train_loitering_model.py        # Loitering model training script
│   ├── train_spoofing_model.py         # Spoofing model training script
│   │
│   └── 📁 venv/                        # Python Virtual Environment
│       ├── bin/                        # Executables
│       ├── include/                    # Header files
│       ├── lib/                        # Installed packages
│       └── pyvenv.cfg                  # Virtual env config
│
├── 📁 app/                             # Additional App Module (Root Level)
│   └── 📁 core/
│       └── 📁 pipeline/
│           ├── __init__.py
│           └── clean_ais.py            # AIS data cleaning pipeline
│
├── 📁 data/                            # Root Level Data Directory
│   ├── cleaned_ais_compressed_24_01_01.csv
│   ├── cleaned_ais_compressed_24_01_01 (2).csv
│   ├── cleaned_ais_compressed_24_01_01 (2).numbers
│   └── compressed_ais_data.csv
│
├── 📁 public/                          # Static Assets
│   └── Leviathan-logo.jpeg             # Project logo
│
├── 📁 node_modules/                    # Frontend Dependencies (Generated)
│   └── [npm packages]
│
└── 📁 venv/                            # Root Level Python Virtual Environment
    └── [Python packages]
```

## Key Directories Explained

### Frontend (`src/`)
- **React 18** application with Vite build tool
- **Components**: Reusable UI components for dashboard, map, charts, etc.
- **Utils**: Helper functions for API calls and map projections
- Uses **Tailwind CSS** for styling and **Recharts** for data visualization

### Backend (`leviathan-backend/`)
- **FastAPI** Python web framework
- **Core Modules**: Business logic for anomaly detection, data processing
- **ML Models**: Pre-trained scikit-learn models for loitering/spoofing detection
- **Routes**: REST API endpoints for frontend communication
- **Data**: Storage for AIS datasets and job results

### AWS Amplify (`amplify/`)
- Infrastructure as code for AWS services
- **Auth**: Cognito authentication configuration
- **Storage**: S3 storage configuration
- **CloudFormation**: AWS resource templates

### Data Directories
- **`data/`** (root): Sample datasets
- **`leviathan-backend/data/`**: Backend data storage with job results
- **`leviathan-backend/data/jobs/`**: Individual job outputs stored by UUID

## Technology Stack Summary

### Frontend
- React 18.3.1
- Vite 5.4.1
- Tailwind CSS 3.4.10
- Recharts 2.15.1
- MapLibre GL 5.17.0
- AWS Amplify 6.16.0
- Material-UI 6.0.2

### Backend
- FastAPI 0.128.0
- Python 3.12/3.13
- scikit-learn 1.8.0
- Pandas 3.0.0
- NumPy 2.4.1
- Geopy 2.4.1
- Uvicorn 0.40.0

### Infrastructure
- AWS Amplify (Auth, Storage)
- AWS S3 (Data storage)
- AWS Cognito (Authentication)

## File Count Summary

- **Frontend Components**: 7 React components
- **Backend Routes**: 5 API route modules
- **Core Modules**: 6 Python core modules
- **ML Models**: 3 pickle files
- **Data Files**: Multiple CSV and parquet files
- **Configuration**: 10+ config files

## Important Entry Points

1. **Frontend**: `src/main.jsx` → `src/App.jsx`
2. **Backend**: `leviathan-backend/entry.py`
3. **Model Training**: 
   - `leviathan-backend/train_loitering_model.py`
   - `leviathan-backend/train_spoofing_model.py`

## Development Workflow

1. **Start Backend**: `cd leviathan-backend && uvicorn entry:app --reload`
2. **Start Frontend**: `pnpm run dev` (from root)
3. **Build Frontend**: `pnpm run build`
4. **Lint Frontend**: `pnpm run lint`
