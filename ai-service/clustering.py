"""
clustering.py
─────────────
Groups similar log messages together using K-Means clustering.

Example output:
  Cluster 1 (8 logs): "Database connection issues"
    - "DB timeout after 3000ms"
    - "Connection pool exhausted"
    - "Failed to acquire DB connection"
    ...
  Cluster 2 (5 logs): "Authentication failures"
    - "Auth token expired"
    - "Invalid credentials for user"
    ...
"""

import json
import re

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize


# Structured-log field names to skip when picking label words
_META_FIELDS = {
    "log", "level", "timestamp", "service", "host", "trace", "thread",
    "message", "ecs", "version", "name", "type", "field", "logger",
    "process", "container", "kubernetes", "stream", "tags",
}

# Common stop words + log-level words that don't add meaning to a cluster label
_STOP_WORDS = {
    "the", "a", "an", "is", "in", "at", "to", "for", "of", "and", "or",
    "with", "from", "by", "on", "has", "have", "was", "were", "be", "been",
    "this", "that", "it", "info", "debug", "warn", "warning", "error",
    "trace", "fatal", "critical", "null", "true", "false", "none",
    "could", "would", "should", "will", "into", "out", "via",
}


def _extract_text(msg: str) -> str:
    """If a log message is JSON, pull the human-readable field out of it."""
    if not msg:
        return ""
    s = msg.strip()
    if not (s.startswith("{") and s.endswith("}")):
        return msg
    try:
        obj = json.loads(s)
    except (ValueError, TypeError):
        return msg
    # Try common message-bearing fields used by structured loggers
    for key in ("message", "msg", "event.original", "log.message", "@message"):
        v = obj.get(key)
        if isinstance(v, str) and v:
            return v
    nested = obj.get("event")
    if isinstance(nested, dict) and isinstance(nested.get("original"), str):
        return nested["original"]
    return msg


def _strip_log_noise(text: str) -> str:
    """Remove timestamps, JSON syntax, paths, numbers — leave plain English."""
    # ISO timestamps and dates
    text = re.sub(r"\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}[\d.,:ZzTt+\- ]*", " ", text)
    # @timestamp and similar
    text = re.sub(r"@\w+", " ", text)
    # Dotted field names: log.level, ecs.version, com.foo.Bar
    text = re.sub(r"\b\w+(?:\.\w+)+\b", " ", text)
    # URLs and Windows-style paths
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[A-Za-z]:[\\/]\S+", " ", text)
    # JSON / bracket / quote punctuation
    text = re.sub(r'["{}\[\]<>(),:;=]', " ", text)
    # Standalone numbers
    text = re.sub(r"\b\d+\b", " ", text)
    return text


def cluster_logs(logs: list[dict], embeddings: np.ndarray, n_clusters: int = None) -> list[dict]:
    """
    Groups logs into clusters based on semantic similarity of their messages.

    Args:
        logs:        list of log dicts (with 'message', 'level', 'service' etc.)
        embeddings:  numpy array of shape (n_logs, 1536) from embeddings.py
        n_clusters:  how many groups to create — auto-calculated if None

    Returns:
        list of cluster dicts with keys: cluster_id, label, count, logs, level_counts
    """

    if len(logs) == 0 or len(embeddings) == 0:
        return []

    n = len(logs)

    # Auto-determine number of clusters based on log count
    # Too few clusters = everything in one group (not useful)
    # Too many clusters = one log per group (not useful)
    if n_clusters is None:
        if n <= 5:
            n_clusters = 1
        elif n <= 20:
            n_clusters = 3
        elif n <= 50:
            n_clusters = 5
        else:
            n_clusters = min(8, n // 10)  # roughly 10 logs per cluster

    # Normalize embeddings — makes clustering more accurate
    # Each vector becomes unit length, so distance = angle between vectors
    normalized = normalize(embeddings)

    # Run K-Means clustering
    kmeans = KMeans(
        n_clusters=n_clusters,
        random_state=42,        # fixed seed = reproducible results
        n_init=10               # run 10 times, pick best result
    )
    labels = kmeans.fit_predict(normalized)

    # Group logs by their cluster label
    clusters = {}
    for i, label in enumerate(labels):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(logs[i])

    # Format clusters for the frontend
    result = []
    for cluster_id, cluster_logs in clusters.items():
        # Count logs by level within this cluster
        level_counts = {"ERROR": 0, "WARN": 0, "INFO": 0}
        for log in cluster_logs:
            level = log.get("level", "INFO")
            if level in level_counts:
                level_counts[level] += 1

        # Generate a label by finding the most common words in this cluster
        label = generate_cluster_label(cluster_logs)

        result.append({
            "cluster_id": int(cluster_id),
            "label": label,
            "count": len(cluster_logs),
            "level_counts": level_counts,
            # Only send top 5 logs per cluster to keep response small
            "sample_logs": cluster_logs[:5]
        })

    # Sort by count — largest cluster first
    result.sort(key=lambda x: x["count"], reverse=True)

    return result


def generate_cluster_label(logs: list[dict]) -> str:
    """
    Generates a short human-readable label for a cluster.

    Steps:
      1. Pull human-readable text out of JSON-structured messages.
      2. Strip timestamps, JSON syntax, paths, numbers.
      3. Pick the 3 most common meaningful words.
    """
    # 1. Concatenate cleaned text from every log in the cluster
    text_parts = []
    for log in logs:
        msg = _extract_text(log.get("message", ""))
        text_parts.append(_strip_log_noise(msg))
    text = " ".join(text_parts).lower()

    # 2. Tokenize, keep only alphabetic words ≥ 4 chars, exclude metadata/stop
    word_freq: dict[str, int] = {}
    for raw in text.split():
        word = re.sub(r"[^a-z]", "", raw)
        if len(word) <= 3:
            continue
        if word in _STOP_WORDS or word in _META_FIELDS:
            continue
        word_freq[word] = word_freq.get(word, 0) + 1

    if not word_freq:
        return "Log Cluster"

    top_words = sorted(word_freq, key=word_freq.get, reverse=True)[:3]
    return " ".join(w.capitalize() for w in top_words)