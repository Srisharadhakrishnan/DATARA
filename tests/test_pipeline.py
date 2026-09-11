import os
import time
import requests
import pytest

API_URL = os.getenv("API_URL", "http://localhost:8000")
SAMPLE_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "sample_data", "customers.csv")

def test_01_health_check():
    """Verify /health returns genuine service connectivity."""
    response = requests.get(f"{API_URL}/health")
    assert response.status_code == 200, f"Health check failed: {response.text}"
    data = response.json()
    assert data["status"] == "ok"
    assert data["kafka_connected"] is True
    assert data["neo4j_connected"] is True

def test_02_ingest_valid_csv():
    """Verify uploading valid CSV returns job_id and status queued."""
    with open(SAMPLE_CSV_PATH, "rb") as f:
        response = requests.post(f"{API_URL}/ingest", files={"file": ("customers.csv", f, "text/csv")})
    
    assert response.status_code == 202, f"Ingest failed: {response.text}"
    data = response.json()
    assert "job_id" in data
    assert data["rows_received"] == 7
    assert data["status"] == "queued"
    return data["job_id"]

def test_03_job_status_completion():
    """Verify polling /status transitions to complete."""
    job_id = test_02_ingest_valid_csv()
    
    # Poll status until complete or timeout
    max_retries = 20
    status_data = None
    for _ in range(max_retries):
        res = requests.get(f"{API_URL}/status?job_id={job_id}")
        assert res.status_code == 200
        status_data = res.json()
        if status_data["status"] == "complete":
            break
        time.sleep(1)

    assert status_data["status"] == "complete", f"Job failed to complete: {status_data}"
    assert status_data["rows_loaded"] == 7
    assert status_data["rows_failed"] == 0

def test_04_grounded_chat_query():
    """Verify chatbot answers grounded query backed by Neo4j data."""
    # First ingest customers.csv to be sure
    test_03_job_status_completion()

    payload = {"question": "How many rows belong to the Billing group?"}
    response = requests.post(f"{API_URL}/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert data["grounded"] is True
    assert "cypher" in data
    assert "result" in data
    assert "3" in data["answer"] or "Billing" in data["answer"]

def test_05_ungrounded_chat_query():
    """Verify unsupported / off-topic question returns grounded=false."""
    payload = {"question": "What is the capital of France?"}
    response = requests.post(f"{API_URL}/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["grounded"] is False
    assert data["answer"] == "I don't have that information in the uploaded data."
    assert data["result"] == []

def test_06_idempotent_reupload():
    """Verify uploading identical file twice does not create duplicate rows."""
    job1_id = test_02_ingest_valid_csv()
    
    # Wait for completion
    for _ in range(20):
        r1 = requests.get(f"{API_URL}/status?job_id={job1_id}").json()
        if r1["status"] == "complete":
            break
        time.sleep(1)

    # Ingest same file second time
    job2_id = test_02_ingest_valid_csv()
    for _ in range(20):
        r2 = requests.get(f"{API_URL}/status?job_id={job2_id}").json()
        if r2["status"] == "complete":
            break
        time.sleep(1)

    # Query count of rows in Billing group via Chat API
    chat_res = requests.post(f"{API_URL}/chat", json={"question": "How many total rows are in the dataset?"}).json()
    assert chat_res["grounded"] is True
    # Count should still be exactly 7, not 14!
    assert "7" in chat_res["answer"]

def test_07_invalid_file_handling():
    """Verify empty file and non-CSV inputs return 400 Bad Request."""
    # Empty CSV
    res_empty = requests.post(f"{API_URL}/ingest", files={"file": ("empty.csv", b"", "text/csv")})
    assert res_empty.status_code == 400

    # Non-CSV file
    res_text = requests.post(f"{API_URL}/ingest", files={"file": ("test.txt", b"hello world", "text/plain")})
    assert res_text.status_code == 400

if __name__ == "__main__":
    pytest.main(["-v", __file__])
