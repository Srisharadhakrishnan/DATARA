from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class IngestResponse(BaseModel):
    job_id: str
    rows_received: int
    status: str

class StatusResponse(BaseModel):
    job_id: str
    status: str
    rows_total: int
    rows_loaded: int
    rows_failed: int

class HealthResponse(BaseModel):
    status: str
    kafka_connected: bool
    neo4j_connected: bool

class ChatRequest(BaseModel):
    question: str = Field(..., example="How many rows belong to the Billing group?")

class ChatResponse(BaseModel):
    answer: str
    cypher: str
    result: List[Dict[str, Any]]
    grounded: bool
