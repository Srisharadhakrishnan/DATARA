# DATARA

> *"Ask your data. Trust the answer."*

Datara is a dynamic CSV-to-knowledge-graph data pipeline with an explainable, grounded natural-language chatbot. Upload any arbitrary CSV file, stream its rows asynchronously through Apache Kafka, ingest them idempotently into Neo4j, and query your database naturally with guaranteed data grounding and zero hallucinations.

---

## 🌟 Key Features

1. **Dynamic CSV Ingestion**: Accepts arbitrary CSV files with dynamic schemas. Columns are never hardcoded.
2. **Kafka Asynchronous Pipeline**: Uploaded CSV rows flow strictly via Kafka (`csv-rows` topic) to a dedicated Loader service before being written to Neo4j. The API upload handler never writes directly to Neo4j.
3. **Idempotent Graph Ingestion**: Every dataset generates a deterministic SHA-256 ID, and rows are ingested using Cypher `MERGE`. Re-uploading identical datasets yields zero duplicate nodes or relationships.
4. **Grounded Chatbot Engine**: Answers natural-language questions strictly using read-only Cypher queries against stored Neo4j nodes.
5. **Data Trust Indicator**: Every chatbot response visually highlights whether it is `✓ GROUNDED IN YOUR DATA` or `! NOT FOUND IN YOUR DATA`. If data is missing or out of scope, Datara responds honestly: *"I don't have that information in the uploaded data."*
6. **Explainable Answers**: Users can expand any answer to inspect the exact Cypher query executed and the raw Cypher JSON result set.
7. **Smart CSV Preview**: Immediate client-side and server-side preview displaying file metadata, row/column counts, detected schema tags, sample data table, and live pipeline stage progress (`CSV ✓ -> Kafka ✓ -> Loader ✓ -> Neo4j ✓`).

---

## 🏗️ Architecture

```
                                    +--------------------+
                                    |     Browser UI     |
                                    |    (React/Vite)    |
                                    +---------+----------+
                                              |
                                   POST /ingest | POST /chat
                                              v
                                    +--------------------+
                                    |    FastAPI API     |
                                    +---------+----------+
                                              |
                                        pub | topic: csv-rows
                                              v
                                    +--------------------+
                                    | Apache Kafka 3.7.0 |
                                    |    (KRaft mode)    |
                                    +---------+----------+
                                              |
                                        sub | group: datara-neo4j-loader-group
                                              v
                                    +--------------------+
                                    |   Python Loader    |
                                    +---------+----------+
                                              |
                                      MERGE | Bolt driver
                                              v
                                    +--------------------+
                                    | Neo4j 5.24 Comm.   |
                                    +--------------------+
```

---

## 🛠️ Technology Stack

- **Frontend**: React 18, Vite, Lucide Icons, Nginx reverse proxy.
- **Backend API**: Python 3.11, FastAPI, Uvicorn, Pydantic v2.
- **Streaming Pipeline**: Apache Kafka 3.7.0 (KRaft mode, single broker, no ZooKeeper).
- **Graph Database**: Neo4j 5.24 Community Edition (Bolt protocol).
- **Containerization**: Docker & Docker Compose (`docker-compose.yml`).

---

## 📁 Project Structure

```
DATARA/
├── docker-compose.yml       # Orchestrates UI, API, Kafka, Loader, Neo4j
├── .env                     # Environment variables
├── .env.example             # Configuration template
├── README.md                # System documentation
├── sample_data/             # Sample CSV files for testing
│   ├── customers.csv
│   └── employees.csv
├── api/                     # FastAPI backend service
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py          # FastAPI application entrypoint
│       ├── models/          # Pydantic schemas
│       ├── routes/          # API route handlers (/ingest, /status, /health, /chat)
│       └── services/        # Neo4j client, Kafka producer, Chat engine
├── loader/                  # Kafka consumer ingestion service
│   ├── Dockerfile
│   ├── requirements.txt
│   └── loader.py            # Streaming Kafka consumer & Neo4j MERGE writer
├── ui/                      # React SaaS frontend
│   ├── Dockerfile
│   ├── nginx.conf           # Reverse proxy configuration
│   ├── package.json
│   ├── index.html
│   └── src/                 # React components & SaaS styles
└── tests/                   # End-to-end integration test suite
    └── test_pipeline.py
```

---

## ⚙️ Environment Variables

| Variable | Default Value | Description |
|---|---|---|
| `NEO4J_URI` | `bolt://neo4j:7687` | Neo4j Bolt connection URI |
| `NEO4J_USER` | `neo4j` | Database username |
| `NEO4J_PASSWORD` | `datara_secure_password_123` | Database password |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker bootstrap address |
| `KAFKA_TOPIC` | `csv-rows` | Kafka topic for CSV row messages |
| `API_PORT` | `8000` | FastAPI server port |
| `UI_PORT` | `3000` | Web UI port |

---

## 🚀 How to Run the Complete Stack

### Prerequisites
- Docker Engine 20+ and Docker Compose v2+ installed.

### Step 1: Clone & Navigate to Repository
```bash
git clone https://github.com/Srisharadhakrishnan/DATARA.git
cd DATARA
```

### Step 2: Launch Docker Compose
```bash
docker compose up --build -d
```

This starts all five services:
- **`ui`**: http://localhost:3000
- **`api`**: http://localhost:8000
- **`neo4j`**: http://localhost:7474 (Browser) / `bolt://localhost:7687`
- **`kafka`**: `localhost:9092`
- **`loader`**: Background worker

### Step 3: Verify System Readiness
Check the system health endpoint:
```bash
curl http://localhost:8000/health
```
**Expected Response:**
```json
{
  "status": "ok",
  "kafka_connected": true,
  "neo4j_connected": true
}
```

---

## 💻 How to Use Datara

1. Open **http://localhost:3000** in your browser.
2. Drag and drop a CSV file (e.g. `sample_data/customers.csv`) into the dropzone.
3. Click **Ingest CSV Data**.
4. View the **Smart CSV Preview** metadata, schema tags, sample rows, and live pipeline stage progress bar.
5. In the **Ask your data** section, enter questions such as:
   - *"How many total rows are in the dataset?"*
   - *"How many rows belong to the Billing group?"*
   - *"List unique values of department"*
6. Review the answer, the **Data Trust Indicator** (`✓ GROUNDED IN YOUR DATA`), and expand **View Cypher** or **View raw result**.

---

## 📡 API Specification

### 1. `GET /health`
Probes genuine connectivity to Kafka and Neo4j.
**Response (200 OK):**
```json
{
  "status": "ok",
  "kafka_connected": true,
  "neo4j_connected": true
}
```

### 2. `POST /ingest`
Accepts a multipart CSV upload. Publishes row events to Kafka topic `csv-rows`.
**Request:** `multipart/form-data` with field `file`.
**Response (202 Accepted):**
```json
{
  "job_id": "job_a1b2c3d4",
  "rows_received": 7,
  "status": "queued"
}
```

### 3. `GET /status?job_id=job_a1b2c3d4`
Retrieves real-time loading progress directly from Neo4j status store.
**Response (200 OK):**
```json
{
  "job_id": "job_a1b2c3d4",
  "status": "complete",
  "rows_total": 7,
  "rows_loaded": 7,
  "rows_failed": 0
}
```

### 4. `POST /chat`
Executes read-only Cypher queries generated dynamically from natural-language questions.
**Request:**
```json
{
  "question": "How many rows belong to the Billing group?"
}
```
**Response (200 OK):**
```json
{
  "answer": "There are 3 rows where group = 'Billing'.",
  "cypher": "MATCH (r:Row) WHERE toLower(toString(r.`group`)) = toLower('Billing') RETURN count(r) AS count",
  "result": [
    {
      "count": 3
    }
  ],
  "grounded": true
}
```

If question cannot be answered from stored Neo4j data:
```json
{
  "answer": "I don't have that information in the uploaded data.",
  "cypher": "MATCH (r:Row) RETURN count(r)",
  "result": [],
  "grounded": false
}
```

---

## 🧪 Automated Testing

Datara includes an automated end-to-end integration test suite.

To run tests against a running Docker stack:
```bash
python -m pytest tests/test_pipeline.py -v
```

---

## 🛡️ Grounding & Security Guarantees

- **Read-Only Cypher**: Chat queries are filtered against mutation keywords (`CREATE`, `MERGE`, `SET`, `DELETE`, `DROP`, `APOC`).
- **No Direct Ingestion**: Uploaded CSV files never bypass Kafka.
- **Strict Grounding**: The system never hallucinates answers or uses external LLM general knowledge as truth.

---

## 📄 License
MIT License - DATARA Open Source Project.
