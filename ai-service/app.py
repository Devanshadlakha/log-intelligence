"""
app.py
──────
Flask entry point — defines all API routes for the AI service.

Routes:
  POST /analyze     ← main endpoint React calls with NL query
  GET  /health      ← health check
"""

import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from query_parser import parse_query
from embeddings import get_embeddings
from clustering import cluster_logs
from summarizer import generate_summary, answer_question, generate_report
from hybrid_search import hybrid_rerank
from anomaly_detection import detect_anomalies
import cache

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Allow React frontend (port 5173) to call this API
CORS(app, origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(","))

# Spring Boot backend URL
SPRING_BACKEND_URL = os.getenv("SPRING_BACKEND_URL", "http://localhost:8080")

# Maps frontend source categories to collector service name prefixes.
# These prefixes are used with Elasticsearch prefix queries so that
# each category page shows ONLY logs from its own collectors.
SOURCE_SERVICE_MAP = {
    "system":    ["windows-event"],
    "file":      ["test-app", "file-"],
    "database":  ["mariadb", "mysql", "postgresql"],
    "docker":    ["docker"],
    "github":    ["github-actions"],
    "webserver": ["nginx", "apache"],
}


# ─────────────────────────────────────────────────────────────
# POST /analyze
# Main endpoint — takes natural language query, returns everything
# ─────────────────────────────────────────────────────────────
@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Full pipeline:
    1. Parse natural language query → structured filters
    2. Fetch logs from Spring Boot using those filters (scoped to source category)
    3. Generate embeddings for log messages
    4. Cluster logs by similarity
    5. Generate root cause summary
    6. Return everything to frontend
    """
    data = request.get_json()

    if not data or "query" not in data:
        return jsonify({"error": "Missing 'query' field in request body"}), 400

    # Forward the user's JWT so backend can enforce RBAC
    auth_header = request.headers.get("Authorization", "")

    natural_query = data["query"]
    source = data.get("source")  # e.g. "github", "docker", "system"
    time_range = data.get("timeRange", "24")
    print(f"\n[analyze] Received query: {natural_query} (source={source})")

    # ── Cache check ──────────────────────────────────────────
    # If we've already computed this exact query recently, return it instantly.
    cached = cache.get(natural_query, time_range, source or "")
    if cached:
        print(f"[analyze] Returning cached result")
        return jsonify(cached)

    # ── Step 1: Parse NL query into structured filters ────────
    filters = parse_query(natural_query)
    print(f"[analyze] Parsed filters: {filters}")

    # Keyword-based level fallback — if the LLM missed an obvious level
    # keyword, detect it here so the user always gets the filter they asked for.
    if not filters.get("level"):
        q_lower = natural_query.lower()
        if any(w in q_lower for w in ["error", "errors", "failure", "failures", "failed", "exception"]):
            filters["level"] = "ERROR"
        elif any(w in q_lower for w in ["warning", "warnings", "warn"]):
            filters["level"] = "WARN"
        elif any(w in q_lower for w in ["info", "information"]):
            filters["level"] = "INFO"

    # IMPORTANT: The frontend's timeRange dropdown takes priority over
    # whatever the LLM parsed from the text. The user explicitly selected
    # the time range, so we trust that over the LLM's guess.
    try:
        filters["hoursAgo"] = float(time_range)
    except (ValueError, TypeError):
        filters["hoursAgo"] = 24
    print(f"[analyze] Time range override: {filters['hoursAgo']} hours")

    # If a source category is specified, attach service patterns for scoping
    if source and source in SOURCE_SERVICE_MAP:
        filters["servicePatterns"] = SOURCE_SERVICE_MAP[source]
        # Don't let GPT's guessed service override the source scope
        filters["service"] = None

    intent = filters.get("intent", "search")
    print(f"[analyze] Intent: {intent}")

    # ── Step 2: Fetch logs from Spring Boot ───────────────────
    logs = fetch_logs_from_backend(filters, auth_header=auth_header)
    print(f"[analyze] Fetched {len(logs)} logs from backend")

    # ── Step 2.5: Hybrid re-ranking ─────────────────────────
    # Re-rank logs using semantic similarity to the user's query.
    # This pushes the most relevant logs to the top, even if ES
    # keyword matching ranked them lower.
    if logs and len(logs) > 3:
        logs = hybrid_rerank(natural_query, logs)
        print(f"[analyze] Logs re-ranked via hybrid search")

    if not logs:
        return jsonify({
            "intent": intent,
            "filters": filters,
            "logs": [],
            "clusters": [],
            "summary": "No logs found matching your query. Try adjusting the time range or filters.",
            "total": 0,
            "metrics": {"time_series": build_time_series([], filters.get("hoursAgo", 24))},
            "anomaly": {"has_anomaly": False, "message": "No logs to analyze.", "anomalies": []}
        })

    # ── Step 2.6: Anomaly detection ─────────────────────────
    # Check for sudden error spikes using Z-score statistics.
    # Runs once here, result is included in all intent responses.
    anomaly_result = detect_anomalies(logs)
    if anomaly_result["has_anomaly"]:
        print(f"[analyze] ANOMALY: {anomaly_result['message']}")
    else:
        print(f"[analyze] No anomalies detected")

    # ── Handle different intents ─────────────────────────────

    if intent == "question":
        # Answer the user's question using log data as context
        answer = answer_question(logs, natural_query)
        print(f"[analyze] Question answered")
        time_series = build_time_series(logs, filters.get("hoursAgo", 24))
        result = {
            "intent": "question",
            "filters": filters,
            "logs": logs,
            "clusters": [],
            "summary": answer,
            "total": len(logs),
            "metrics": {"time_series": time_series},
            "anomaly": anomaly_result
        }
        cache.put(natural_query, time_range, source or "", result)
        return jsonify(result)

    if intent == "report":
        # Generate a comprehensive summary report
        report = generate_report(logs, source)
        print(f"[analyze] Report generated")
        time_series = build_time_series(logs, filters.get("hoursAgo", 24))
        result = {
            "intent": "report",
            "filters": filters,
            "logs": logs,
            "clusters": [],
            "summary": report,
            "total": len(logs),
            "metrics": {"time_series": time_series},
            "anomaly": anomaly_result
        }
        cache.put(natural_query, time_range, source or "", result)
        return jsonify(result)

    # ── Default: search intent ───────────────────────────────

    # Step 3: Generate embeddings (only for ERROR/WARN logs)
    error_logs = [l for l in logs if l.get("level") in ["ERROR", "WARN"]]
    logs_to_embed = error_logs if error_logs else logs[:50]

    clusters = []
    if len(logs_to_embed) >= 2:  # need at least 2 logs to cluster
        messages = [log.get("message", "") for log in logs_to_embed]
        embeddings = get_embeddings(messages)

        # Step 4: Cluster logs
        if len(embeddings) > 0:
            clusters = cluster_logs(logs_to_embed, embeddings)
            print(f"[analyze] Created {len(clusters)} clusters")

    # Step 5: Generate root cause summary
    summary = generate_summary(logs)
    print(f"[analyze] Summary generated")

    # Step 6: Build time-series data for chart (errors/warnings per hour)
    time_series = build_time_series(logs, filters.get("hoursAgo", 24))

    result = {
        "intent": "search",
        "filters": filters,
        "logs": logs,
        "clusters": clusters,
        "summary": summary,
        "total": len(logs),
        "metrics": {"time_series": time_series},
        "anomaly": anomaly_result
    }
    cache.put(natural_query, time_range, source or "", result)
    return jsonify(result)


# ─────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "UP",
        "service": "log-intelligence-ai",
        "cache": cache.get_stats()
    })


# ─────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────

def fetch_logs_from_backend(filters: dict, max_retries: int = 3, auth_header: str = "") -> list:
    """
    Calls the Spring Boot Search API with structured filters.
    Forwards the user's JWT token so the backend can enforce RBAC.
    Retries with exponential backoff on transient failures.

    Args:
        filters:      dict of search filters (level, service, keyword, hoursAgo, etc.)
        max_retries:  number of attempts before returning empty list
        auth_header:  Authorization header from the frontend (forwarded for RBAC)

    Returns:
        list of log dicts, or empty list on failure
    """
    import time

    params = {}

    if filters.get("level"):
        params["level"] = filters["level"]
    if filters.get("service"):
        params["service"] = filters["service"]
    if filters.get("servicePatterns"):
        params["servicePatterns"] = ",".join(filters["servicePatterns"])
    if filters.get("keyword"):
        params["keyword"] = filters["keyword"]

    # Always send hoursAgo — never let the backend default to 24
    params["hoursAgo"] = filters.get("hoursAgo", 24)

    # Forward the user's JWT for RBAC enforcement at the backend
    headers = {}
    if auth_header:
        headers["Authorization"] = auth_header

    print(f"[fetch_logs] Sending to backend: {params}")

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                f"{SPRING_BACKEND_URL}/api/logs/search",
                params=params,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return data.get("logs", [])

        except requests.exceptions.ConnectionError:
            print(f"[fetch_logs] Cannot connect to backend (attempt {attempt}/{max_retries})")
        except requests.exceptions.Timeout:
            print(f"[fetch_logs] Backend timed out (attempt {attempt}/{max_retries})")
        except Exception as e:
            print(f"[fetch_logs] Error: {e} (attempt {attempt}/{max_retries})")

        # Exponential backoff: wait 1s, then 2s before retrying
        if attempt < max_retries:
            wait = attempt  # 1s, 2s
            print(f"[fetch_logs] Retrying in {wait}s...")
            time.sleep(wait)

    print("[fetch_logs] All retries exhausted — returning empty list")
    return []


def build_time_series(logs: list, hours_ago: float = 24) -> list:
    """
    Builds hourly error/warning counts as time-series data for chart rendering.

    Always returns at least 6 hourly buckets (zero-filled for empty slots) so
    the frontend has enough points to render a meaningful line. Buckets cover
    the requested time range, capped at 24 hourly points.

    Returns: [{ "timestamp": "HH:00", "errors": int, "warnings": int }, ...]
    """
    from datetime import datetime, timezone, timedelta

    bucket_count = max(6, min(int(round(hours_ago or 24)), 24))

    now_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    buckets = [now_hour - timedelta(hours=i) for i in range(bucket_count - 1, -1, -1)]
    counts = {b: {"errors": 0, "warnings": 0} for b in buckets}

    for log in logs:
        level = log.get("level", "")
        if level not in ("ERROR", "WARN"):
            continue

        ts_str = log.get("timestamp", "")
        if not ts_str:
            continue

        try:
            if ts_str.endswith("Z"):
                ts_str = ts_str[:-1] + "+00:00"
            dt = datetime.fromisoformat(ts_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            bucket = dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        except Exception:
            continue

        if bucket in counts:
            key = "errors" if level == "ERROR" else "warnings"
            counts[bucket][key] += 1

    # Return ISO-8601 UTC strings so the frontend can format to local time —
    # keeps chart axis aligned with log-table timestamps (which are also local).
    return [
        {
            "timestamp": b.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "errors": int(counts[b]["errors"]),
            "warnings": int(counts[b]["warnings"]),
        }
        for b in buckets
    ]


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))
    print(f"\n[OK] AI Service running on http://localhost:{port}\n")
    app.run(debug=True, host="0.0.0.0", port=port)