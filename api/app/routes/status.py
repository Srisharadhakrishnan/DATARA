from fastapi import APIRouter, HTTPException, Query, status
from app.models.schemas import StatusResponse
from app.services.neo4j_client import neo4j_client

router = APIRouter()

@router.get("/status", response_model=StatusResponse)
def get_job_status(job_id: str = Query(..., description="The ID of the ingestion job")):
    if not job_id or not job_id.strip():
        raise HTTPException(status_code=400, detail="job_id parameter is required.")

    status_data = neo4j_client.get_job_status(job_id.strip())
    if not status_data:
        raise HTTPException(status_code=404, detail=f"Job ID '{job_id}' not found.")

    return StatusResponse(
        job_id=status_data["job_id"],
        status=status_data["status"],
        rows_total=status_data.get("rows_total", 0),
        rows_loaded=status_data.get("rows_loaded", 0),
        rows_failed=status_data.get("rows_failed", 0)
    )
