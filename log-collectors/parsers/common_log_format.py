"""
common_log_format.py
────────────────────
Parses nginx and apache access log lines in Common Log Format (CLF)
and Combined Log Format.

Common:   127.0.0.1 - frank [10/Oct/2000:13:55:36 -0700] "GET /index.html HTTP/1.0" 200 2326
Combined: ... + "http://referrer" "Mozilla/5.0 ..."
"""

import re
from datetime import datetime, timezone, timedelta

# Common Log Format regex
CLF_PATTERN = re.compile(
    r'^(?P<remote_host>\S+)\s+'        # 127.0.0.1
    r'\S+\s+'                           # ident (usually -)
    r'(?P<remote_user>\S+)\s+'         # user (or -)
    r'\[(?P<timestamp>[^\]]+)\]\s+'    # [10/Oct/2000:13:55:36 -0700]
    r'"(?P<method>\S+)\s+'             # "GET
    r'(?P<path>\S+)\s+'               # /index.html
    r'\S+"\s+'                         # HTTP/1.0"
    r'(?P<status>\d{3})\s+'           # 200
    r'(?P<size>\S+)'                   # 2326
)

# Combined format adds referrer and user-agent after CLF
COMBINED_PATTERN = re.compile(
    r'^(?P<remote_host>\S+)\s+'
    r'\S+\s+'
    r'(?P<remote_user>\S+)\s+'
    r'\[(?P<timestamp>[^\]]+)\]\s+'
    r'"(?P<method>\S+)\s+'
    r'(?P<path>\S+)\s+'
    r'\S+"\s+'
    r'(?P<status>\d{3})\s+'
    r'(?P<size>\S+)\s+'
    r'"(?P<referrer>[^"]*)"\s+'
    r'"(?P<user_agent>[^"]*)"'
)


def parse_access_log_line(line: str, fmt: str = "combined") -> dict | None:
    """
    Parse a single access log line.

    Args:
        line: Raw log line
        fmt: "combined" or "common"

    Returns:
        Dict with keys: remote_host, method, path, status (int),
        size, timestamp (datetime), referrer, user_agent, message (formatted).
        Returns None if the line doesn't match.
    """
    pattern = COMBINED_PATTERN if fmt == "combined" else CLF_PATTERN
    match = pattern.match(line.strip())

    if not match:
        return None

    groups = match.groupdict()

    # Parse the CLF timestamp: "10/Oct/2000:13:55:36 -0700"
    timestamp = _parse_clf_timestamp(groups["timestamp"])

    status = int(groups["status"])
    method = groups["method"]
    path = groups["path"]
    remote_host = groups["remote_host"]

    # Build a human-readable message
    message = f"{method} {path} {status}"
    if fmt == "combined" and "user_agent" in groups:
        message += f" - {groups.get('user_agent', '')}"

    return {
        "remote_host": remote_host,
        "method": method,
        "path": path,
        "status": status,
        "size": groups["size"],
        "timestamp": timestamp,
        "referrer": groups.get("referrer"),
        "user_agent": groups.get("user_agent"),
        "message": message,
    }


def status_to_level(status_code: int) -> str:
    """Map HTTP status code to log level."""
    if status_code >= 500:
        return "ERROR"
    elif status_code >= 400:
        return "WARN"
    else:
        return "INFO"


def _parse_clf_timestamp(ts: str) -> datetime:
    """
    Parse CLF timestamp format: "10/Oct/2000:13:55:36 -0700"
    Returns a UTC datetime.
    """
    try:
        dt = datetime.strptime(ts, "%d/%b/%Y:%H:%M:%S %z")
        return dt.astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)
