import csv
import io
import hashlib
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.models.schemas import IngestResponse
from app.services.kafka_producer import kafka_producer
from app.services.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_csv(file: UploadFile = File(...)):
    # 1. Basic File Validation
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")
    
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a valid CSV file.")

    try:
        content_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {str(e)}")

    if len(content_bytes.strip()) == 0:
        raise HTTPException(status_code=400, detail="Uploaded CSV file is empty.")

    # 2. Parse CSV
    try:
        text_stream = io.StringIO(content_bytes.decode("utf-8-sig", errors="replace"))
        reader = csv.DictReader(text_stream)
        
        if not reader.fieldnames:
            raise HTTPException(status_code=400, detail="CSV missing header row or contains invalid formatting.")
        
        fieldnames = [f.strip() for f in reader.fieldnames if f and f.strip()]
        if not fieldnames:
            raise HTTPException(status_code=400, detail="CSV header contains no valid column names.")

        rows = []
        for idx, row in enumerate(reader, start=1):
            # Clean string values
            clean_row = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k and k.strip()}
            if clean_row:
                rows.append((idx, clean_row))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Malformed CSV file: {str(e)}")

    if len(rows) == 0:
        raise HTTPException(status_code=400, detail="CSV file contains headers but zero data rows.")

    # 3. Deterministic Dataset ID and Job ID
    content_hash = hashlib.sha256(content_bytes).hexdigest()[:16]
    dataset_id = f"ds_{content_hash}"
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    filename = file.filename

    # 4. Create JobStatus in Neo4j
    try:
        neo4j_client.create_job_status(
            job_id=job_id,
            dataset_id=dataset_id,
            filename=filename,
            rows_total=len(rows)
        )
    except Exception as e:
        logger.error(f"Failed to create job status in Neo4j: {e}")
        raise HTTPException(status_code=500, detail="Failed to register ingestion job in database.")

    # 5. Publish CSV Rows to Kafka
    published_count = 0
    kafka_items = []
    for row_index, row_data in rows:
        row_id = f"{dataset_id}_{row_index}"
        kafka_items.append({
            "job_id": job_id,
            "dataset_id": dataset_id,
            "filename": filename,
            "row_id": row_id,
            "row_index": row_index,
            "row_data": row_data
        })

    try:
        published_count = kafka_producer.publish_batch(kafka_items)
        neo4j_client.update_job_status(job_id, "loading")
    except Exception as e:
        logger.error(f"Failed to publish rows to Kafka: {e}")
        neo4j_client.update_job_status(job_id, "failed")
        raise HTTPException(status_code=500, detail="Failed to publish CSV rows to Kafka pipeline.")

    return IngestResponse(
        job_id=job_id,
        rows_received=len(rows),
        status="queued"
    )
