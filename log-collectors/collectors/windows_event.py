"""
windows_event.py
────────────────
Reads Windows Event Viewer logs (System, Application, Security)
using the pywin32 library. Polls for new events at a configurable interval.
"""

import time
import logging
from datetime import datetime, timezone

from base_collector import BaseCollector

logger = logging.getLogger(__name__)

# Try importing pywin32 — only available on Windows
try:
    import win32evtlog
    import win32evtlogutil
    import win32con
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
    logger.warning("pywin32 not available — Windows Event Log collector will not work")


# Windows event types to our log levels
EVENT_TYPE_MAP = {
    win32con.EVENTLOG_INFORMATION_TYPE: "INFO" if PYWIN32_AVAILABLE else "INFO",
    win32con.EVENTLOG_WARNING_TYPE: "WARN" if PYWIN32_AVAILABLE else "WARN",
    win32con.EVENTLOG_ERROR_TYPE: "ERROR" if PYWIN32_AVAILABLE else "ERROR",
    win32con.EVENTLOG_AUDIT_SUCCESS: "INFO" if PYWIN32_AVAILABLE else "INFO",
    win32con.EVENTLOG_AUDIT_FAILURE: "ERROR" if PYWIN32_AVAILABLE else "ERROR",
} if PYWIN32_AVAILABLE else {}


class WindowsEventCollector(BaseCollector):
    """
    Polls Windows Event Viewer for new events and sends them to Kafka.
    Service name format: "windows-event-{logtype}" (e.g., "windows-event-system")
    """

    def __init__(self, kafka_config: dict, log_types: list = None,
                 poll_interval: int = 5):
        super().__init__(service_name="windows-event-log", kafka_config=kafka_config)
        self.log_types = log_types or ["System", "Application"]
        self.poll_interval = poll_interval
        # Track last record number per log type to avoid reprocessing
        self.last_record = {}

    def map_level(self, raw_level: str) -> str:
        return raw_level  # already mapped before send_log

    def start(self):
        if not PYWIN32_AVAILABLE:
            logger.error("Cannot start Windows Event collector: pywin32 not installed")
            return

        self.running = True
        server = None  # None = local machine

        # Initialize last record positions to current end
        for log_type in self.log_types:
            try:
                handle = win32evtlog.OpenEventLog(server, log_type)
                flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
                total = win32evtlog.GetNumberOfEventLogRecords(handle)
                self.last_record[log_type] = total
                win32evtlog.CloseEventLog(handle)
                logger.info(f"Initialized {log_type} event log at record {total}")
            except Exception as e:
                logger.error(f"Failed to open {log_type} event log: {e}")
                self.last_record[log_type] = 0

        logger.info(f"Polling Windows Event Logs: {self.log_types} every {self.poll_interval}s")

        while self.running:
            for log_type in self.log_types:
                self._poll_log(server, log_type)
            time.sleep(self.poll_interval)

    def _poll_log(self, server, log_type: str):
        """Read new events from a specific Windows event log."""
        try:
            handle = win32evtlog.OpenEventLog(server, log_type)
            flags = win32evtlog.EVENTLOG_FORWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            total = win32evtlog.GetNumberOfEventLogRecords(handle)

            if total <= self.last_record.get(log_type, 0):
                win32evtlog.CloseEventLog(handle)
                return

            events = []
            while True:
                batch = win32evtlog.ReadEventLog(handle, flags, 0)
                if not batch:
                    break
                events.extend(batch)

            # Process only new events
            new_events = events[self.last_record.get(log_type, 0):]
            self.last_record[log_type] = total

            for event in new_events:
                self._process_event(event, log_type)

            win32evtlog.CloseEventLog(handle)

        except Exception as e:
            logger.error(f"Error polling {log_type} event log: {e}")

    def _process_event(self, event, log_type: str):
        """Convert a Windows event to a LogEntry and send to Kafka."""
        try:
            # Get the event message
            try:
                message = win32evtlogutil.SafeFormatMessage(event, log_type)
            except Exception:
                message = f"EventID={event.EventID} Source={event.SourceName}"

            if not message:
                message = f"EventID={event.EventID} Source={event.SourceName}"

            # Truncate very long messages
            if len(message) > 1000:
                message = message[:1000] + "..."

            # Map event type to level
            level = EVENT_TYPE_MAP.get(event.EventType, "INFO")

            # Windows event TimeGenerated components are in LOCAL time.
            # Build naive local, then convert to UTC for storage.
            local_naive = datetime(
                event.TimeGenerated.year,
                event.TimeGenerated.month,
                event.TimeGenerated.day,
                event.TimeGenerated.hour,
                event.TimeGenerated.minute,
                event.TimeGenerated.second,
            )
            timestamp = local_naive.astimezone(timezone.utc)

            self.send_log(
                level=level,
                message=f"[{event.SourceName}] {message}",
                timestamp=timestamp,
                host=self.hostname,
                service_override=f"windows-event-{log_type.lower()}",
            )
        except Exception as e:
            logger.error(f"Error processing event: {e}")

    def send_log(self, level, message, timestamp=None, host=None, trace_id=None,
                 service_override=None):
        """Override to allow per-event service name."""
        original = self.service_name
        if service_override:
            self.service_name = service_override
        super().send_log(level, message, timestamp, host, trace_id)
        self.service_name = original
