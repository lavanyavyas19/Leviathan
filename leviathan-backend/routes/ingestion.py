from fastapi import APIRouter, BackgroundTasks
from app.core.ingestion_engine import run_ingestion_pipeline
from app.schemas.ingestion_schema import IngestionRequest

router = APIRouter(prefix="/ingest", tags=["Data Ingestion"])

@router.post("/")
async def start_ingestion(request: IngestionRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_ingestion_pipeline, request.source_path)
    return {"status": "Ingestion started", "source": request.source_path}
