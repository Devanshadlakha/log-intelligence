"""
database.py
───────────
Tails MySQL and PostgreSQL log files and sends parsed entries to Kafka.

MySQL log types:
  - General query log: all SQL statements
  - Slow query log: queries exceeding long_query_time
  - Error log: server errors and warnings

PostgreSQL log lines start with a timestamp and level prefix:
  2026-04-10 14:23:45.123 UTC [12345] LOG: statement: SELECT ...
  2026-04-10 14:23:45.123 UTC [12345] ERROR: relation "foo" does not exist
"""

import os
import re
import time
import logging
from datetime import datetime, timezone

from base_collector import BaseCollector

logger = logging.getLogger(__name__)

# ── MySQL patterns ──────────────────────────────────────────────

# General/slow query log timestamp line: "2026-04-10T14:23:45.123456Z"
MYSQL_TIMESTAMP_PATTERN = re.compile(
    r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\s+(\d+)\s+(\w+)\s+(.*)'
)

# MySQL error log: "2026-04-10T14:23:45.123456Z 0 [ERROR] [MY-000001] ..."
MYSQL_ERROR_PATTERN = re.compile(
    r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\s+\d+\s+\[(\w+)\]\s+(.*)'
)

# Slow query header: "# Time: 2026-04-10T14:23:45.123456Z"
MYSQL_SLOW_TIME = re.compile(r'^# Time:\s+(.*)')
MYSQL_SLOW_QUERY = re.compile(r'^# Query_time:\s+(\S+)\s+Lock_time:\s+(\S+)\s+Rows_sent:\s+(\d+)\s+Rows_examined:\s+(\d+)')

# ── PostgreSQL patterns ─────────────────────────────────────────

# Standard PG log line: "2026-04-10 14:23:45.123 UTC [12345] LOG:  statement: ..."
PG_LOG_PATTERN = re.compile(
    r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \w+)\s+'
    r'\[\d+\]\s+'
    r'(\w+):\s+'
    r'(.*)'
)


class DatabaseCollector(BaseCollector):
    """
    Tails database log files (MySQL or PostgreSQL) and sends entries to Kafka.
    """

    MYSQL_LEVEL_MAP = {
        "QUERY": "INFO",
        "CONNECT": "INFO",
        "QUIT": "INFO",
        "INIT": "INFO",
        "NOTE": "INFO",
        "WARNING": "WARN",
        "ERROR": "ERROR",
        "SYSTEM": "INFO",
    }

    PG_LEVEL_MAP = {
        "LOG": "INFO",
        "INFO": "INFO",
        "NOTICE": "INFO",
        "DEBUG": "INFO",
        "WARNING": "WARN",
        "ERROR": "ERROR",
        "FATAL": "ERROR",
        "PANIC": "ERROR",
    }

    def __init__(self, service_name: str, kafka_config: dict,
                 db_type: str, log_path: str):
        super().__init__(service_name, kafka_config)
        self.db_type = db_type.lower()  # "mysql" or "postgresql"
        self.log_path = log_path
        self.file_position = 0

    def map_level(self, raw_level: str) -> str:
        level_map = self.MYSQL_LEVEL_MAP if self.db_type == "mysql" else self.PG_LEVEL_MAP
        return level_map.get(raw_level.upper(), "INFO")

    def start(self):
        self.running = True

        if not os.path.exists(self.log_path):
            logger.warning(f"Database log not found: {self.log_path}. Waiting...")
            while self.running and not os.path.exists(self.log_path):
                time.sleep(5)

        if not self.running:
            return

        # Start tailing from the end of the file
        self.file_position = os.path.getsize(self.log_path)
        logger.info(f"Tailing {self.db_type} log: {self.log_path}")

        while self.running:
            self._read_new_lines()
            time.sleep(1)

    def _read_new_lines(self):
        try:
            file_size = os.path.getsize(self.log_path)

            if file_size < self.file_position:
                logger.info(f"Log rotation detected for {self.log_path}")
                self.file_position = 0

            if file_size == self.file_position:
                return

            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self.file_position)
                new_lines = f.readlines()
                self.file_position = f.tell()

            for line in new_lines:
                line = line.strip()
                if not line:
                    continue

                if self.db_type == "mysql":
                    self._process_mysql_line(line)
                else:
                    self._process_pg_line(line)

        except Exception as e:
            logger.error(f"Error reading {self.log_path}: {e}")

    def _process_mysql_line(self, line: str):
        """Parse a MySQL log line."""
        # Try error log format first
        match = MYSQL_ERROR_PATTERN.match(line)
        if match:
            ts_str, level, message = match.groups()
            timestamp = self._parse_mysql_timestamp(ts_str)
            self.send_log(level=level, message=message, timestamp=timestamp)
            return

        # Try general/slow query log format
        match = MYSQL_TIMESTAMP_PATTERN.match(line)
        if match:
            ts_str, thread_id, command, args = match.groups()
            timestamp = self._parse_mysql_timestamp(ts_str)
            message = f"[{command}] {args}" if args else command
            self.send_log(level=command, message=message, timestamp=timestamp)
            return

        # Slow query indicators
        if line.startswith("# Query_time"):
            match = MYSQL_SLOW_QUERY.match(line)
            if match:
                query_time, lock_time, rows_sent, rows_examined = match.groups()
                message = f"Slow query: time={query_time}s lock={lock_time}s rows_sent={rows_sent} rows_examined={rows_examined}"
                self.send_log(level="WARN", message=message)
                return

        # Skip comment lines and other non-log lines
        if line.startswith("#") or line.startswith("/*"):
            return

        # SQL statement continuation — send as INFO
        if len(line) > 5:
            self.send_log(level="INFO", message=line)

    def _process_pg_line(self, line: str):
        """Parse a PostgreSQL log line."""
        match = PG_LOG_PATTERN.match(line)
        if match:
            ts_str, level, message = match.groups()
            timestamp = self._parse_pg_timestamp(ts_str)
            self.send_log(level=level, message=message, timestamp=timestamp)
        elif len(line) > 5:
            # Continuation line or non-standard format
            self.send_log(level="INFO", message=line)

    def _parse_mysql_timestamp(self, ts_str: str) -> datetime:
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)

    def _parse_pg_timestamp(self, ts_str: str) -> datetime:
        """Parse: '2026-04-10 14:23:45.123 UTC'"""
        try:
            # Remove timezone name and parse
            parts = ts_str.rsplit(" ", 1)
            dt = datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S.%f")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return datetime.now(timezone.utc)
