"""
main.py
───────
CLI entry point for log collectors.
Loads config.yaml, starts enabled collectors in separate threads.

Usage:
    python main.py                        # start all enabled collectors
    python main.py --collector file_watcher  # start only one collector
"""

import argparse
import logging
import signal
import sys
import threading

import yaml
from dotenv import load_dotenv

from collectors.file_watcher import FileWatcherCollector
from collectors.windows_event import WindowsEventCollector
from collectors.web_server import WebServerCollector
from collectors.github_actions import GitHubActionsCollector
from collectors.database import DatabaseCollector
from collectors.docker_logs import DockerLogCollector

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("main")


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def build_collectors(config: dict, only: str = None) -> list:
    """Instantiate enabled collectors from config."""
    kafka_cfg = config.get("kafka", {})
    collectors_cfg = config.get("collectors", {})
    instances = []

    # ── File Watcher ─────────────────────────────────────────
    if _should_start("file_watcher", collectors_cfg, only):
        for entry in collectors_cfg["file_watcher"].get("paths", []):
            c = FileWatcherCollector(
                service_name=entry.get("service_name", "file-log"),
                kafka_config=kafka_cfg,
                file_path=entry["path"],
                pattern=entry.get("pattern"),
                min_level=entry.get("min_level", "INFO"),
            )
            instances.append(c)

    # ── Windows Event Log ────────────────────────────────────
    if _should_start("windows_event", collectors_cfg, only):
        cfg = collectors_cfg["windows_event"]
        c = WindowsEventCollector(
            kafka_config=kafka_cfg,
            log_types=cfg.get("log_types", ["System", "Application"]),
            poll_interval=cfg.get("poll_interval_seconds", 5),
        )
        instances.append(c)

    # ── Web Server Logs ──────────────────────────────────────
    if _should_start("web_server", collectors_cfg, only):
        for entry in collectors_cfg["web_server"].get("files", []):
            c = WebServerCollector(
                service_name=entry.get("service_name", "web-server"),
                kafka_config=kafka_cfg,
                file_path=entry["path"],
                log_format=entry.get("format", "combined"),
                min_level=entry.get("min_level", "INFO"),
            )
            instances.append(c)

    # ── GitHub Actions ───────────────────────────────────────
    if _should_start("github_actions", collectors_cfg, only):
        cfg = collectors_cfg["github_actions"]
        c = GitHubActionsCollector(
            kafka_config=kafka_cfg,
            repositories=cfg.get("repositories", []),
            poll_interval=cfg.get("poll_interval_seconds", 60),
        )
        instances.append(c)

    # ── Database Logs ────────────────────────────────────────
    if _should_start("database", collectors_cfg, only):
        for src in collectors_cfg["database"].get("sources", []):
            c = DatabaseCollector(
                service_name=src.get("service_name", src["type"]),
                kafka_config=kafka_cfg,
                db_type=src["type"],
                log_path=src["log_path"],
            )
            instances.append(c)

    # ── Docker Logs ──────────────────────────────────────────
    if _should_start("docker", collectors_cfg, only):
        cfg = collectors_cfg["docker"]
        c = DockerLogCollector(
            kafka_config=kafka_cfg,
            container_names=cfg.get("containers", []),
            labels=cfg.get("labels", {}),
            min_level=cfg.get("min_level", "WARN"),
        )
        instances.append(c)

    return instances


def _should_start(name: str, collectors_cfg: dict, only: str) -> bool:
    """Check if a collector should be started based on config and CLI filter."""
    if only and only != name:
        return False
    cfg = collectors_cfg.get(name, {})
    return cfg.get("enabled", False)


def main():
    parser = argparse.ArgumentParser(description="Log Intelligence - Log Collectors")
    parser.add_argument(
        "--collector",
        type=str,
        default=None,
        help="Start only this collector (e.g., file_watcher, windows_event, docker)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    instances = build_collectors(config, only=args.collector)

    if not instances:
        logger.warning("No collectors enabled. Check config.yaml and enable at least one.")
        sys.exit(1)

    logger.info(f"Starting {len(instances)} collector(s)...")

    # Start each collector in its own daemon thread
    threads = []
    for c in instances:
        t = threading.Thread(target=c.start, name=c.__class__.__name__, daemon=True)
        t.start()
        threads.append((c, t))
        logger.info(f"  Started: {c.__class__.__name__} (service={c.service_name})")

    # Graceful shutdown on Ctrl+C
    shutdown_event = threading.Event()

    def handle_signal(sig, frame):
        logger.info("Shutdown signal received...")
        for c, _ in threads:
            c.stop()
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    logger.info("All collectors running. Press Ctrl+C to stop.")
    shutdown_event.wait()
    logger.info("All collectors stopped.")


if __name__ == "__main__":
    main()
