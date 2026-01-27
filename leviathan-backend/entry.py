
from app.routes.ingestion import router as ingestion_router
from app.routes.loitering import router as loitering_router
from app.routes.spoofing import router as spoofing_router
from app.routes.job import router as job_router

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI(title="Leviathan Backend")

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# Routes
# --------------------------------------------------
app.include_router(ingestion_router, prefix="/api")
app.include_router(job_router, prefix="/api")      # /api/jobs/*
app.include_router(spoofing_router, prefix="/api")
app.include_router(loitering_router, prefix="/api")

# --------------------------------------------------
# Health check
# --------------------------------------------------
@app.get("/")
def root():
    return {"message": "Leviathan Backend is running!"}
