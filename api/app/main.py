import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import health, ingest, status, chat
from app.services.neo4j_client import neo4j_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("datara-api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Datara API service...")
    try:
        neo4j_client.init_db()
    except Exception as e:
        logger.warning(f"Could not init Neo4j on startup: {e}")
    yield
    logger.info("Shutting down Datara API service...")
    neo4j_client.close()

app = FastAPI(
    title="Datara Grounded Knowledge API",
    description="Ask your data. Trust the answer.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(status.router)
app.include_router(chat.router)

@app.get("/")
def root():
    return {
        "service": "DATARA API",
        "tagline": "Ask your data. Trust the answer.",
        "status": "online"
    }
