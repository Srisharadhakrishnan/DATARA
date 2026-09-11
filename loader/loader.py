import os
import json
import time
import logging
from kafka import KafkaConsumer
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] DataraLoader: %(message)s")
logger = logging.getLogger("loader")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "datara_secure_password_123")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "csv-rows")

def get_neo4j_driver():
    while True:
        try:
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            driver.verify_connectivity()
            logger.info("Connected to Neo4j successfully.")
            return driver
        except Exception as e:
            logger.warning(f"Waiting for Neo4j... ({e})")
            time.sleep(3)

def get_kafka_consumer():
    while True:
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
                group_id="datara-neo4j-loader-group",
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8"))
            )
            logger.info(f"Connected to Kafka and subscribed to topic '{KAFKA_TOPIC}'.")
            return consumer
        except Exception as e:
            logger.warning(f"Waiting for Kafka... ({e})")
            time.sleep(3)

def process_row(driver, data: dict):
    job_id = data.get("job_id")
    dataset_id = data.get("dataset_id")
    filename = data.get("filename")
    row_id = data.get("row_id")
    row_index = data.get("row_index")
    row_data = data.get("row_data", {})

    cypher_success = """
    MERGE (d:Dataset {id: $dataset_id})
    ON CREATE SET d.filename = $filename, d.uploaded_at = timestamp()
    WITH d
    MERGE (r:Row {id: $row_id})
    SET r += $row_data, r.dataset_id = $dataset_id, r.row_index = $row_index
    MERGE (d)-[:HAS_ROW]->(r)
    WITH d
    MATCH (j:JobStatus {job_id: $job_id})
    SET j.rows_loaded = j.rows_loaded + 1,
        j.status = CASE
            WHEN (j.rows_loaded + j.rows_failed + 1) >= j.rows_total THEN 'complete'
            ELSE 'loading'
        END
    """
    
    cypher_fail = """
    MATCH (j:JobStatus {job_id: $job_id})
    SET j.rows_failed = j.rows_failed + 1,
        j.status = CASE
            WHEN (j.rows_loaded + j.rows_failed + 1) >= j.rows_total THEN 'complete'
            ELSE 'loading'
        END
    """

    try:
        with driver.session() as session:
            session.run(
                cypher_success,
                dataset_id=dataset_id,
                filename=filename,
                row_id=row_id,
                row_index=row_index,
                row_data=row_data,
                job_id=job_id
            )
    except Exception as e:
        logger.error(f"Failed to process row {row_id} into Neo4j: {e}")
        try:
            with driver.session() as session:
                session.run(cypher_fail, job_id=job_id)
        except Exception as inner_e:
            logger.error(f"Failed to update row_failed status: {inner_e}")

def main():
    logger.info("Starting Datara Loader Service...")
    driver = get_neo4j_driver()
    consumer = get_kafka_consumer()

    try:
        for message in consumer:
            data = message.value
            process_row(driver, data)
    except Exception as e:
        logger.error(f"Fatal error in consumer loop: {e}")
    finally:
        driver.close()
        consumer.close()

if __name__ == "__main__":
    main()
