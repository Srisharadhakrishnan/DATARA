from fastapi import APIRouter, Response, status
from app.models.schemas import HealthResponse
from app.services.kafka_producer import kafka_producer
from app.services.neo4j_client import neo4j_client

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
def health_check(response: Response):
    kafka_ok = kafka_producer.check_health()
    neo4j_ok = neo4j_client.check_health()
    
    is_healthy = kafka_ok and neo4j_ok
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
    return HealthResponse(
        status="ok" if is_healthy else "degraded",
        kafka_connected=kafka_ok,
        neo4j_connected=neo4j_ok
    )
