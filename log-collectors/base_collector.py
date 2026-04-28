"""
base_collector.py
─────────────────
Abstract base class for all log collectors.
Handles Kafka producer setup, LogEntry JSON construction, and lifecycle.
"""

import abc
import json
import uuid
import logging
import socket
from datetime import datetime, timezone

from kafka import KafkaProducer


class BaseCollector(abc.ABC):
    """
    Base class all collectors inherit from.

    Subclasses must implement:
        - start()     : Begin collecting logs (blocking or threaded)
        - stop()      : Graceful shutdown
        - map_level() : Map source-specific level string to INFO|WARN|ERROR
    """

    def __init__(self, service_name: str, kafka_config: dict):
        self.service_name = service_name
        self.hostname = socket.gethostname()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.running = False

        bootstrap = kafka_config.get("bootstrap_servers", "localhost:9092")
        self.topic = kafka_config.get("topic", "app-logs")

        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8"),
            retries=3,
        )

    def send_log(self, level: str, message: str, timestamp: datetime = None,
                 host: str = None, trace_id: str = None):
        """
        Build a LogEntry dict and send it to Kafka.

        Args:
            level: Raw level string from the source (will be mapped via map_level)
            message: The log message text
            timestamp: When the log was generated (defaults to now UTC)
            host: Optional hostname override (defaults to this machine's hostname)
            trace_id: Optional trace/correlation ID
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        entry = {
            "id": str(uuid.uuid4()),
            "service": self.service_name,
            "level": self._normalize_level(level),
            "message": message,
            "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%S.")
                         + f"{timestamp.microsecond // 1000:03d}Z",
            "host": host or self.hostname,
            "traceId": trace_id,
        }

        try:
            self.producer.send(self.topic, key=entry["id"], value=entry)
        except Exception as e:
            self.logger.error(f"Failed to send log to Kafka: {e}")

    def _normalize_level(self, raw_level: str) -> str:
        """Map the raw level through the subclass and validate."""
        mapped = self.map_level(raw_level)
        return mapped if mapped in ("INFO", "WARN", "ERROR") else "INFO"

    @abc.abstractmethod
    def map_level(self, raw_level: str) -> str:
        """Map a source-specific log level to INFO, WARN, or ERROR."""

    @abc.abstractmethod
    def start(self):
        """Begin collecting logs. Should set self.running = True."""

    def stop(self):
        """Graceful shutdown — flush and close Kafka producer."""
        self.running = False
        self.logger.info(f"Stopping {self.__class__.__name__}...")
        try:
            self.producer.flush(timeout=5)
            self.producer.close(timeout=5)
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
