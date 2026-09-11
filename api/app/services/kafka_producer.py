import os
import json
import logging
from typing import Dict, Any, Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "csv-rows")

class DataraKafkaProducer:
    def __init__(self):
        self._producer: Optional[KafkaProducer] = None

    def get_producer(self) -> KafkaProducer:
        if self._producer is None:
            self._producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                retries=5,
                request_timeout_ms=10000
            )
        return self._producer

    def close(self):
        if self._producer is not None:
            try:
                self._producer.flush()
                self._producer.close()
            except Exception as e:
                logger.warning(f"Error closing Kafka producer: {e}")
            self._producer = None

    def check_health(self) -> bool:
        try:
            producer = self.get_producer()
            # Test getting metadata for topic or cluster
            topics = producer.partitions_for(KAFKA_TOPIC)
            return True
        except Exception as e:
            logger.warning(f"Kafka health check failed: {e}")
            return False

    def publish_row(self, key: str, value: Dict[str, Any]) -> bool:
        try:
            producer = self.get_producer()
            future = producer.send(KAFKA_TOPIC, key=key, value=value)
            future.get(timeout=10)
            return True
        except Exception as e:
            logger.error(f"Failed to publish Kafka message: {e}")
            return False

    def publish_batch(self, items: list) -> int:
        published = 0
        producer = self.get_producer()
        for item in items:
            key = item.get("row_id")
            producer.send(KAFKA_TOPIC, key=key, value=item)
            published += 1
        producer.flush()
        return published

kafka_producer = DataraKafkaProducer()
