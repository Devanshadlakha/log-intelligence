"""
docker_logs.py
──────────────
Streams logs from Docker containers in real-time using the Docker SDK.
Each container's log stream runs in a separate thread.
Service name format: "docker-{container_name}"
"""

import re
import time
import logging
import threading
from datetime import datetime, timezone

import docker
from docker.errors import NotFound, APIError

from base_collector import BaseCollector

logger = logging.getLogger(__name__)

# Try to extract a log level from a container's log line
LEVEL_PATTERN = re.compile(
    r'\b(TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL)\b',
    re.IGNORECASE,
)


class DockerLogCollector(BaseCollector):
    """
    Streams logs from running Docker containers and sends them to Kafka.
    Discovers containers on startup and monitors for new ones.
    """

    LEVEL_MAP = {
        "TRACE": "INFO",
        "DEBUG": "INFO",
        "INFO": "INFO",
        "WARN": "WARN",
        "WARNING": "WARN",
        "ERROR": "ERROR",
        "CRITICAL": "ERROR",
        "FATAL": "ERROR",
    }

    LEVEL_RANK = {"INFO": 0, "WARN": 1, "ERROR": 2}

    def __init__(self, kafka_config: dict, container_names: list = None,
                 labels: dict = None, min_level: str = "WARN"):
        super().__init__(service_name="docker", kafka_config=kafka_config)
        self.container_names = container_names or []
        self.labels = labels or {}
        self.min_level = min_level.upper() if min_level else "WARN"
        self.min_rank = self.LEVEL_RANK.get(self.min_level, 1)
        self.client = None
        self.stream_threads = {}  # container_id -> thread

    def map_level(self, raw_level: str) -> str:
        return self.LEVEL_MAP.get(raw_level.upper(), "INFO")

    def start(self):
        self.running = True

        try:
            self.client = docker.from_env()
            self.client.ping()
        except Exception as e:
            logger.error(f"Cannot connect to Docker daemon: {e}")
            return

        logger.info("Connected to Docker daemon. Discovering containers...")

        # Main loop: discover containers and start streaming
        while self.running:
            self._discover_and_stream()
            time.sleep(10)  # re-check for new containers every 10s

    def stop(self):
        super().stop()
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass

    def _discover_and_stream(self):
        """Find containers matching our filters and start log streams."""
        try:
            filters = {}
            if self.labels:
                filters["label"] = [f"{k}={v}" for k, v in self.labels.items()]

            containers = self.client.containers.list(filters=filters)

            for container in containers:
                # If specific names were given, only stream those
                if self.container_names and container.name not in self.container_names:
                    continue

                cid = container.id
                if cid not in self.stream_threads or not self.stream_threads[cid].is_alive():
                    t = threading.Thread(
                        target=self._stream_container,
                        args=(container,),
                        daemon=True,
                        name=f"docker-{container.name}",
                    )
                    t.start()
                    self.stream_threads[cid] = t
                    logger.info(f"Streaming logs from container: {container.name}")

        except APIError as e:
            logger.error(f"Docker API error: {e}")

    def _stream_container(self, container):
        """Stream logs from a single container."""
        container_name = container.name
        service = f"docker-{container_name}"

        try:
            for log_bytes in container.logs(stream=True, follow=True,
                                            since=int(time.time()),
                                            timestamps=True):
                if not self.running:
                    break

                line = log_bytes.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                timestamp, message = self._parse_docker_log_line(line)
                level = self._extract_level(message)

                # Drop low-importance lines so app containers don't flood the index.
                if self.LEVEL_RANK.get(level, 0) < self.min_rank:
                    continue

                self.send_log(
                    level=level,
                    message=message,
                    timestamp=timestamp,
                    host=container_name,
                )

        except NotFound:
            logger.info(f"Container {container_name} was removed")
        except Exception as e:
            if self.running:
                logger.error(f"Error streaming {container_name}: {e}")

    def _parse_docker_log_line(self, line: str):
        """
        Docker log lines with timestamps look like:
        2026-04-10T14:23:45.123456789Z actual log message here
        """
        # Try to split off the Docker timestamp prefix
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[0].endswith("Z") and "T" in parts[0]:
            try:
                # Docker timestamps have nanosecond precision — truncate to microseconds
                ts_str = parts[0][:26] + "Z"
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                return ts, parts[1]
            except ValueError:
                pass

        return datetime.now(timezone.utc), line

    def _extract_level(self, message: str) -> str:
        """Try to extract a log level from the message text."""
        match = LEVEL_PATTERN.search(message)
        if match:
            return match.group(1).upper()
        return "INFO"
