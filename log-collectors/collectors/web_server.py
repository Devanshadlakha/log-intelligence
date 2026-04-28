"""
web_server.py
─────────────
Tails nginx or apache access log files and sends parsed entries to Kafka.
Reuses the file-tailing approach from file_watcher with a specialized
access log parser.
"""

import os
import time
import logging

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from base_collector import BaseCollector
from parsers.common_log_format import parse_access_log_line, status_to_level

logger = logging.getLogger(__name__)


class WebServerCollector(BaseCollector):
    """
    Tails nginx/apache access logs and sends parsed entries to Kafka.
    Level is derived from HTTP status code (2xx/3xx=INFO, 4xx=WARN, 5xx=ERROR).
    """

    LEVEL_RANK = {"INFO": 0, "WARN": 1, "ERROR": 2}

    def __init__(self, service_name: str, kafka_config: dict,
                 file_path: str, log_format: str = "combined",
                 min_level: str = "INFO"):
        super().__init__(service_name, kafka_config)
        self.file_path = file_path
        self.log_format = log_format
        self.file_position = 0
        self.observer = None
        self.min_level = (min_level or "INFO").upper()
        self.min_rank = self.LEVEL_RANK.get(self.min_level, 0)

    def map_level(self, raw_level: str) -> str:
        # Level is already mapped by status_to_level before calling send_log
        return raw_level

    def start(self):
        self.running = True

        if not os.path.exists(self.file_path):
            logger.warning(f"Access log not found: {self.file_path}. Waiting...")
            while self.running and not os.path.exists(self.file_path):
                time.sleep(2)

        if os.path.exists(self.file_path):
            self.file_position = os.path.getsize(self.file_path)

        logger.info(f"Watching access log: {self.file_path} (format={self.log_format})")

        # Poll instead of using watchdog — inotify doesn't fire over Docker
        # Desktop bind mounts on Windows.
        while self.running:
            self.read_new_lines()
            time.sleep(1)

    def stop(self):
        super().stop()

    def read_new_lines(self):
        try:
            file_size = os.path.getsize(self.file_path)

            if file_size < self.file_position:
                logger.info(f"Log rotation detected for {self.file_path}")
                self.file_position = 0

            if file_size == self.file_position:
                return

            with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self.file_position)
                new_lines = f.readlines()
                self.file_position = f.tell()

            for line in new_lines:
                line = line.strip()
                if not line:
                    continue
                self._process_line(line)

        except Exception as e:
            logger.error(f"Error reading {self.file_path}: {e}")

    def _process_line(self, line: str):
        parsed = parse_access_log_line(line, self.log_format)

        if parsed:
            level = status_to_level(parsed["status"])
            if self.LEVEL_RANK.get(level, 0) < self.min_rank:
                return
            self.send_log(
                level=level,
                message=parsed["message"],
                timestamp=parsed["timestamp"],
                host=parsed["remote_host"],
            )
        else:
            if self.min_rank > 0:
                return
            self.send_log(level="INFO", message=line)


class _AccessLogHandler(FileSystemEventHandler):
    def __init__(self, collector: WebServerCollector, filename: str):
        super().__init__()
        self.collector = collector
        self.filename = filename

    def on_modified(self, event):
        if event.is_directory:
            return
        if os.path.basename(event.src_path) == self.filename:
            self.collector.read_new_lines()
