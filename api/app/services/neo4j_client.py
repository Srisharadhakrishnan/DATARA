import os
import logging
from typing import Dict, Any, List, Optional
from neo4j import GraphDatabase, Driver

logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "datara_secure_password_123")

class Neo4jClient:
    def __init__(self):
        self._driver: Optional[Driver] = None

    def get_driver(self) -> Driver:
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
        return self._driver

    def close(self):
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def check_health(self) -> bool:
        try:
            driver = self.get_driver()
            driver.verify_connectivity()
            with driver.session() as session:
                session.run("RETURN 1").single()
            return True
        except Exception as e:
            logger.warning(f"Neo4j health check failed: {e}")
            return False

    def init_db(self):
        """Create constraints for dataset, row, and job status nodes."""
        try:
            driver = self.get_driver()
            with driver.session() as session:
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Dataset) REQUIRE d.id IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (r:Row) REQUIRE r.id IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (j:JobStatus) REQUIRE j.job_id IS UNIQUE")
        except Exception as e:
            logger.warning(f"Neo4j database init notice: {e}")

    def create_job_status(self, job_id: str, dataset_id: str, filename: str, rows_total: int):
        driver = self.get_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (j:JobStatus {job_id: $job_id})
                SET j.dataset_id = $dataset_id,
                    j.filename = $filename,
                    j.rows_total = $rows_total,
                    j.rows_loaded = 0,
                    j.rows_failed = 0,
                    j.status = 'queued',
                    j.created_at = timestamp()
                """,
                job_id=job_id,
                dataset_id=dataset_id,
                filename=filename,
                rows_total=rows_total
            )

    def update_job_status(self, job_id: str, status: str):
        driver = self.get_driver()
        with driver.session() as session:
            session.run(
                "MATCH (j:JobStatus {job_id: $job_id}) SET j.status = $status",
                job_id=job_id, status=status
            )

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        driver = self.get_driver()
        with driver.session() as session:
            result = session.run(
                """
                MATCH (j:JobStatus {job_id: $job_id})
                RETURN j.job_id AS job_id, j.status AS status,
                       j.rows_total AS rows_total, j.rows_loaded AS rows_loaded,
                       j.rows_failed AS rows_failed
                """,
                job_id=job_id
            )
            record = result.single()
            if record:
                return dict(record)
            return None

    def get_dataset_schema(self) -> List[str]:
        """Retrieve all property keys present on :Row nodes."""
        driver = self.get_driver()
        with driver.session() as session:
            result = session.run(
                """
                MATCH (r:Row)
                WITH keys(r) AS k
                UNWIND k AS key
                WITH DISTINCT key
                WHERE NOT key IN ['id', 'dataset_id', 'row_index']
                RETURN key
                """
            )
            return [record["key"] for record in result]

    def get_row_properties_sample(self) -> Dict[str, List[Any]]:
        """Retrieve distinct values for property keys to enable dynamic natural query matching."""
        driver = self.get_driver()
        prop_values = {}
        keys = self.get_dataset_schema()
        with driver.session() as session:
            for k in keys:
                res = session.run(
                    f"MATCH (r:Row) WHERE r.`{k}` IS NOT NULL RETURN DISTINCT r.`{k}` AS val LIMIT 50"
                )
                prop_values[k] = [rec["val"] for rec in res]
        return prop_values

    def execute_read_cypher(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        driver = self.get_driver()
        with driver.session() as session:
            result = session.run(cypher, params or {})
            records = []
            for record in result:
                records.append(dict(record))
            return records

neo4j_client = Neo4jClient()
