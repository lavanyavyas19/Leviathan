from fastapi import FastAPI
from app.routes import spoofing, loitering

app = FastAPI(title="LEVIATHAN Anomaly Engine")

app.include_router(spoofing.router)
app.include_router(loitering.router)

@app.get("/")
def home():
    return {"message": "LEVIATHAN anomaly engine is running"}
