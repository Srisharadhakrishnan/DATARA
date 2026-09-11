import os
import time
import requests
import pytest

API_URL = os.getenv("API_URL", "http://localhost:8000")
SAMPLE_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "sample_data", "datara_sample.csv")

def test_01_health_check():
    """Verify /health returns genuine service connectivity."""
    response = requests.get(f"{API_URL}/health")
    assert response.status_code == 200, f"Health check failed: {response.text}"
    data = response.json()
    assert data["status"] == "ok"
    assert data["kafka_connected"] is True
    assert data["neo4j_connected"] is True

def test_02_ingest_datara_sample():
    """Ingest datara_sample.csv with 7 data rows."""
    with open(SAMPLE_CSV_PATH, "rb") as f:
        response = requests.post(f"{API_URL}/ingest", files={"file": ("datara_sample.csv", f, "text/csv")})
    
    assert response.status_code == 202, f"Ingest failed: {response.text}"
    data = response.json()
    job_id = data["job_id"]
    
    # Poll status until complete
    for _ in range(20):
        res = requests.get(f"{API_URL}/status?job_id={job_id}")
        assert res.status_code == 200
        status_data = res.json()
        if status_data["status"] == "complete":
            break
        time.sleep(1)

    assert status_data["status"] == "complete"
    assert status_data["rows_loaded"] == 7
    return job_id

# TEST CASE 1
def test_03_count_billing():
    """Question: How many customers are in Billing?"""
    res = requests.post(f"{API_URL}/chat", json={"question": "How many customers are in Billing?"}).json()
    assert res["grounded"] is True
    assert "count" in res["cypher"].lower()
    assert "3" in res["answer"]

# TEST CASE 2 & 7
def test_04_show_billing_customers_and_status():
    """Question: Show Billing customers and their status."""
    res = requests.post(f"{API_URL}/chat", json={"question": "Show Billing customers and their status."}).json()
    assert res["grounded"] is True
    assert "billing" in res["cypher"].lower()
    assert len(res["result"]) == 3
    # Check returned keys in result
    first_row = res["result"][0]
    assert "customer_name" in first_row or "customer_id" in first_row
    assert "status" in first_row

# TEST CASE 3
def test_05_show_support_and_order_amounts():
    """Question: Show Support customers and their order amounts."""
    res = requests.post(f"{API_URL}/chat", json={"question": "Show Support customers and their order amounts."}).json()
    assert res["grounded"] is True
    assert "support" in res["cypher"].lower()
    assert len(res["result"]) == 2
    first_row = res["result"][0]
    assert "order_amount" in first_row

# TEST CASE 4
def test_06_show_sales_and_order_ids():
    """Question: Show Sales customers with their order IDs."""
    res = requests.post(f"{API_URL}/chat", json={"question": "Show Sales customers with their order IDs."}).json()
    assert res["grounded"] is True
    assert "sales" in res["cypher"].lower()
    assert len(res["result"]) == 2
    first_row = res["result"][0]
    assert "order_id" in first_row

# TEST CASE 5
def test_07_customers_from_chennai():
    """Question: Which customers are from Chennai?"""
    res = requests.post(f"{API_URL}/chat", json={"question": "Which customers are from Chennai?"}).json()
    assert res["grounded"] is True
    assert "chennai" in res["cypher"].lower()
    assert len(res["result"]) == 3

# TEST CASE 6
def test_08_customers_in_hr_ungrounded():
    """Question: How many customers are in HR? (HR does not exist)"""
    res = requests.post(f"{API_URL}/chat", json={"question": "How many customers are in HR?"}).json()
    assert res["grounded"] is False
    assert res["answer"] == "I don't have that information in the uploaded data."
    assert res["result"] == []

# TEST CASE 8
def test_09_case_insensitivity_variations():
    """Test capitalization variations of queries."""
    q1 = requests.post(f"{API_URL}/chat", json={"question": "show billing customers"}).json()
    q2 = requests.post(f"{API_URL}/chat", json={"question": "SHOW BILLING CUSTOMERS"}).json()
    q3 = requests.post(f"{API_URL}/chat", json={"question": "Show Billing customers"}).json()

    assert q1["grounded"] is True
    assert q2["grounded"] is True
    assert q3["grounded"] is True
    assert len(q1["result"]) == len(q2["result"]) == len(q3["result"]) == 3

if __name__ == "__main__":
    pytest.main(["-v", __file__])
