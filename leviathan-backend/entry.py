from fastapi import FastAPI
from routes import spoofing, loitering, ingestion

app = FastAPI(title="Leviathan Backend")

# Include Routers
app.include_router(spoofing.router, prefix="/api/spoofing", tags=["Spoofing Detection"])
app.include_router(loitering.router, prefix="/api/loitering", tags=["Loitering Detection"])
app.include_router(ingestion.router, prefix="/api/ingestion", tags=["Data Ingestion"])

@app.get("/")
def root():
    return {"message": "Leviathan Backend is running!"}

