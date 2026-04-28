"""
file_watcher.py
───────────────
Watches log files on disk using the watchdog library.
Tails new lines as they are appended and sends them to Kafka.
Handles log rotation (file truncated or replaced).
"""

import os
import re
import time
import logging
from datetime import datetime, timezone

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from base_collector import BaseCollector

logger = logging.getLogger(__name__)

# Default pattern: "2026-04-10 14:23:45 ERROR Something went wrong"
DEFAULT_PATTERN = (
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>\w+)\s+"
    r"(?P<message>.+)$"
)


class FileWatcherCollector(BaseCollector):
    """
    Tails a log file and sends new lines to Kafka.
    Uses watchdog to detect file modifications efficiently.
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

    def __init__(self, service_name: str, kafka_config: dict,
                 file_path: str, pattern: str = None, min_level: str = "INFO"):
        super().__init__(service_name, kafka_config)
        self.file_path = file_path
        self.pattern = re.compile(pattern or DEFAULT_PATTERN)
        self.file_position = 0
        self.observer = None
        self.min_level = (min_level or "INFO").upper()
        self.min_rank = self.LEVEL_RANK.get(self.min_level, 0)

    def map_level(self, raw_level: str) -> str:
        return self.LEVEL_MAP.get(raw_level.upper(), "INFO")

    def start(self):
        self.running = True

        if not os.path.exists(self.file_path):
            logger.warning(f"File not found: {self.file_path}. Waiting for it to appear...")
            self._wait_for_file()

        # Seek to end of file so we only tail new content
        if os.path.exists(self.file_path):
            self.file_position = os.path.getsize(self.file_path)

        logger.info(f"Watching file: {self.file_path}")

        # Poll for new content. Watchdog's inotify backend doesn't fire on
        # Docker Desktop Windows-host bind mounts, so polling is required for
        # the collector to work both on real Linux filesystems and on bind
        # mounts from Windows hosts.
        while self.running:
            self.read_new_lines()
            time.sleep(1)

    def stop(self):
        super().stop()

    def _wait_for_file(self):
        """Block until the watched file appears on disk."""
        while self.running and not os.path.exists(self.file_path):
            time.sleep(2)

    def read_new_lines(self):
        """Read any new lines appended to the file since last read."""
        try:
            file_size = os.path.getsize(self.file_path)

            # Detect rotation: file got smaller → reset to beginning
            if file_size < self.file_position:
                logger.info(f"File rotation detected for {self.file_path}")
                self.file_position = 0

            if file_size == self.file_position:
                return  # no new data

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
        """Parse a log line and send it to Kafka."""
        match = self.pattern.match(line)

        if match:
            groups = match.groupdict()
            level = groups.get("level", "INFO")
            message = groups.get("message", line)
            ts_str = groups.get("timestamp")

            timestamp = None
            if ts_str:
                try:
                    timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
        else:
            level = "INFO"
            message = line
            timestamp = None

        normalized = self._normalize_level(level)
        if self.LEVEL_RANK.get(normalized, 0) < self.min_rank:
            return

        self.send_log(level=level, message=message, timestamp=timestamp)


class _FileChangeHandler(FileSystemEventHandler):
    """Watchdog handler that triggers line reading on file modification."""

    def __init__(self, collector: FileWatcherCollector, filename: str):
        super().__init__()
        self.collector = collector
        self.filename = filename

    def on_modified(self, event):
        if event.is_directory:
            return
        if os.path.basename(event.src_path) == self.filename:
            self.collector.read_new_lines()
