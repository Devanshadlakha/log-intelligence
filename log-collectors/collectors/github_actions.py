"""
github_actions.py
─────────────────
Polls the GitHub API for workflow run logs.
Tracks completed runs and sends job/step results to Kafka.
Service name format: "github-actions-{repo}"
"""

import os
import time
import logging
from datetime import datetime, timezone

import requests

from base_collector import BaseCollector

logger = logging.getLogger(__name__)


class GitHubActionsCollector(BaseCollector):
    """
    Polls GitHub Actions API for workflow runs and sends
    job results to Kafka.
    """

    CONCLUSION_LEVEL_MAP = {
        "success": "INFO",
        "neutral": "INFO",
        "cancelled": "WARN",
        "skipped": "WARN",
        "timed_out": "ERROR",
        "failure": "ERROR",
        "action_required": "WARN",
        "stale": "WARN",
    }

    def __init__(self, kafka_config: dict, repositories: list = None,
                 poll_interval: int = 60):
        super().__init__(service_name="github-actions", kafka_config=kafka_config)
        self.repositories = repositories or []
        self.poll_interval = poll_interval
        self.token = os.getenv("GITHUB_TOKEN")
        self.seen_runs = set()  # track run IDs we've already processed

        if not self.token:
            logger.warning("GITHUB_TOKEN not set — API rate limits will be very low (60 req/hr)")

    def map_level(self, raw_level: str) -> str:
        return self.CONCLUSION_LEVEL_MAP.get(raw_level.lower(), "INFO")

    def start(self):
        self.running = True

        if not self.repositories:
            logger.error("No repositories configured for GitHub Actions collector")
            return

        logger.info(
            f"Polling GitHub Actions for {len(self.repositories)} repo(s) "
            f"every {self.poll_interval}s"
        )

        # Seed only the runs older than ~10 min so recent activity still
        # surfaces on first poll. Without this, a restart silently swallows
        # any in-flight CI runs.
        for repo in self.repositories:
            self._seed_seen_runs(repo)

        while self.running:
            for repo in self.repositories:
                self._poll_repo(repo)
            time.sleep(self.poll_interval)

    def _get_headers(self) -> dict:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _seed_seen_runs(self, repo: dict):
        """Mark old runs as already-seen, but allow recent ones to emit on first poll."""
        owner = repo["owner"]
        name = repo["repo"]
        cutoff = datetime.now(timezone.utc).timestamp() - 600  # 10 minutes ago

        try:
            resp = requests.get(
                f"https://api.github.com/repos/{owner}/{name}/actions/runs",
                headers=self._get_headers(),
                params={"per_page": 20},
                timeout=15,
            )
            resp.raise_for_status()

            seeded = 0
            for run in resp.json().get("workflow_runs", []):
                ts = self._parse_gh_timestamp(run.get("created_at"))
                if ts.timestamp() < cutoff:
                    self.seen_runs.add(run["id"])
                    seeded += 1

            logger.info(f"Seeded {seeded} old runs for {owner}/{name} (recent ones will emit on next poll)")

        except Exception as e:
            logger.error(f"Failed to seed runs for {owner}/{name}: {e}")

    def _poll_repo(self, repo: dict):
        """Check for new completed workflow runs."""
        owner = repo["owner"]
        name = repo["repo"]

        try:
            resp = requests.get(
                f"https://api.github.com/repos/{owner}/{name}/actions/runs",
                headers=self._get_headers(),
                params={"per_page": 10},
                timeout=15,
            )
            resp.raise_for_status()

            runs = resp.json().get("workflow_runs", [])

            for run in runs:
                if run["id"] in self.seen_runs:
                    continue
                # Only emit once the run has actually finished.
                if run.get("status") != "completed":
                    continue

                self.seen_runs.add(run["id"])
                self._process_run(owner, name, run)

        except requests.exceptions.RequestException as e:
            logger.error(f"Error polling {owner}/{name}: {e}")

    def _process_run(self, owner: str, repo: str, run: dict):
        """Fetch jobs for a workflow run and send each as a log entry."""
        run_id = run["id"]
        workflow_name = run.get("name", "unknown")
        conclusion = run.get("conclusion", "unknown")
        branch = run.get("head_branch", "unknown")

        try:
            resp = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs",
                headers=self._get_headers(),
                timeout=15,
            )
            resp.raise_for_status()

            jobs = resp.json().get("jobs", [])

            for job in jobs:
                job_name = job.get("name", "unknown")
                job_conclusion = job.get("conclusion", conclusion)
                started = job.get("started_at")
                completed = job.get("completed_at")

                # Build message
                message = (
                    f"Workflow '{workflow_name}' job '{job_name}' {job_conclusion} "
                    f"on branch '{branch}'"
                )

                # Add step details for failures
                if job_conclusion in ("failure", "timed_out"):
                    failed_steps = [
                        s["name"] for s in job.get("steps", [])
                        if s.get("conclusion") == "failure"
                    ]
                    if failed_steps:
                        message += f" | Failed steps: {', '.join(failed_steps)}"

                timestamp = self._parse_gh_timestamp(completed or started)
                level = self.map_level(job_conclusion)
                service = f"github-actions-{repo}"

                # Use service override for repo-specific service name
                original = self.service_name
                self.service_name = service
                self.send_log(
                    level=level,
                    message=message,
                    timestamp=timestamp,
                    trace_id=f"run-{run_id}",
                )
                self.service_name = original

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching jobs for run {run_id}: {e}")

    def _parse_gh_timestamp(self, ts_str: str) -> datetime:
        """Parse GitHub API timestamp: '2026-04-10T14:23:45Z'"""
        if not ts_str:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
