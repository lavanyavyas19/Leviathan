from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ✅ import all routers from app.routes
from app.routes import ingestion, loitering, spoofing

app = FastAPI(title="Leviathan Backend")

# CORS (keep as you had it)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# include routers
app.include_router(spoofing.router,  prefix="/api/spoofing",  tags=["Spoofing Detection"])
app.include_router(loitering.router,  prefix="/api/loitering", tags=["Loitering Detection"])
app.include_router(ingestion.router,  prefix="/api",          tags=["Data Ingestion"])

@app.get("/")
def root():
    return {"message": "Leviathan Backend is running!"}
