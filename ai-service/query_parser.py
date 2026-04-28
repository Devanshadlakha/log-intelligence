"""
query_parser.py
───────────────
Converts a natural language query like:
  "show me payment service errors in the last 6 hours"
Into structured filters like:
  { "level": "ERROR", "service": "payment-service", "hoursAgo": 6, "keyword": null }

Uses OpenAI GPT to understand intent.
"""

import json
import threading
import time
from openai import OpenAI # type: ignore
from dotenv import load_dotenv
import os
import requests

load_dotenv()

# Initialize Groq-compatible client via OpenAI SDK
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

SPRING_BACKEND_URL = os.getenv("SPRING_BACKEND_URL", "http://localhost:8080")

# Dynamic service discovery — fetched from backend, refreshed every 5 minutes
_services_cache = []
_cache_lock = threading.Lock()


def _refresh_services():
    """Fetch distinct service names from the backend."""
    global _services_cache
    try:
        resp = requests.get(f"{SPRING_BACKEND_URL}/api/logs/services", timeout=5)
        if resp.ok:
            services = resp.json().get("services", [])
            if services:
                with _cache_lock:
                    _services_cache = services
                print(f"[query_parser] Refreshed services: {services}")
    except Exception as e:
        print(f"[query_parser] Could not refresh services: {e}")


def _refresh_loop():
    """Background thread that refreshes the service list every 5 minutes."""
    while True:
        _refresh_services()
        time.sleep(300)


# Start the background refresh thread
_refresh_thread = threading.Thread(target=_refresh_loop, daemon=True)
_refresh_thread.start()


def get_valid_services() -> list:
    """Returns the current list of valid services."""
    with _cache_lock:
        return list(_services_cache)


VALID_LEVELS = ["ERROR", "WARN", "INFO"]


def parse_query(natural_language_query: str) -> dict:
    """
    Takes a natural language query and returns structured filters + intent.

    Args:
        natural_language_query: e.g. "show payment errors last 6 hours"

    Returns:
        dict with keys: intent, level, service, keyword, hoursAgo
        intent is one of: "search", "question", "report"
    """

    # Build the prompt dynamically with current service list
    services = get_valid_services()
    services_str = ", ".join(services) if services else "no services discovered yet"
    services_options = (" | ".join(f'"{s}"' for s in services) + " | null") if services else "null"

    system_prompt = f"""
You are a log search query parser.
Determine the user's intent and convert their query into structured JSON.

The system has these services: {services_str}
Log levels available: ERROR, WARN, INFO

Return ONLY a valid JSON object with these exact keys:
{{
  "intent": "search" | "question" | "report",
  "level": "ERROR" | "WARN" | "INFO" | null,
  "service": {services_options},
  "keyword": "search term to match in message" | null,
  "hoursAgo": number (e.g. 0.25, 0.5, 1, 3, 6, 12, 24, 72, 168 — default to 24 if not specified)
}}

Intent rules:
- "search" → user wants to fetch/show/list specific logs (e.g. "show errors", "get docker logs", "find timeout messages")
- "question" → user is asking a question about their logs or system (e.g. "what's causing errors?", "is my system healthy?", "why is the database slow?", "how many errors today?")
- "report" → user wants a summary or overview report (e.g. "generate a report", "give me a summary", "overview of all logs", "daily report")

Filter rules:
- If user mentions "error" or "errors" or "failures" → level = "ERROR"
- If user mentions "warning" or "warnings" → level = "WARN"
- If user mentions a service name (partial is fine e.g. "nginx" → "nginx", "docker" → match any docker service, "github" → "github-actions")
- If user says "last 15 minutes" → hoursAgo = 0.25
- If user says "last 30 minutes" or "last half hour" → hoursAgo = 0.5
- If user says "last hour" or "past hour" → hoursAgo = 1
- If user says "last 3 hours" → hoursAgo = 3
- If user says "last 6 hours" → hoursAgo = 6
- If user says "last 12 hours" → hoursAgo = 12
- If user says "last 24 hours" or "today" → hoursAgo = 24
- If user says "last 3 days" → hoursAgo = 72
- If user says "last week" or "last 7 days" → hoursAgo = 168
- Extract any specific keyword to search in messages
- Return null for fields that are not mentioned
- Return ONLY the JSON, no explanation, no markdown
"""

    user_prompt = f"Parse this log query: {natural_language_query}"

    # Retry LLM call up to 2 times on transient failures
    for attempt in range(1, 4):  # 3 total attempts
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0,
                max_tokens=200
            )

            raw = response.choices[0].message.content.strip()
            filters = json.loads(raw)
            filters = sanitize_filters(filters)
            return filters

        except json.JSONDecodeError as e:
            print(f"[query_parser] JSON parse error: {e}")
            return default_filters()

        except Exception as e:
            print(f"[query_parser] LLM error (attempt {attempt}/3): {e}")
            if attempt < 3:
                time.sleep(1)

    # All retries failed — use safe defaults so the pipeline still works
    print("[query_parser] All LLM retries failed — using default filters")
    return default_filters()


VALID_INTENTS = ["search", "question", "report"]


def sanitize_filters(filters: dict) -> dict:
    """
    Ensures filters only contain valid values.
    Prevents injection or invalid queries.
    """
    sanitized = {}

    # Validate intent
    intent = filters.get("intent", "search")
    sanitized["intent"] = intent if intent in VALID_INTENTS else "search"

    # Validate level
    level = filters.get("level")
    sanitized["level"] = level if level in VALID_LEVELS else None

    # Validate service
    service = filters.get("service")
    sanitized["service"] = service if service in get_valid_services() else None

    # Validate keyword — just ensure it's a string or None
    keyword = filters.get("keyword")
    sanitized["keyword"] = str(keyword)[:100] if keyword else None  # max 100 chars

    # Validate hoursAgo — must be a positive number
    try:
        hours = float(filters.get("hoursAgo", 24))
        sanitized["hoursAgo"] = hours if 0 < hours <= 720 else 24  # max 30 days
    except (ValueError, TypeError):
        sanitized["hoursAgo"] = 24

    return sanitized


def default_filters() -> dict:
    """Returns safe defaults when parsing fails."""
    return {
        "intent": "search",
        "level": None,
        "service": None,
        "keyword": None,
        "hoursAgo": 24
    }