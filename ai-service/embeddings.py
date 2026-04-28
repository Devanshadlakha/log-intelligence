"""
embeddings.py
─────────────
Converts log messages into numerical vectors (embeddings) using a local model.

Uses sentence-transformers (runs locally, no API key needed).

Why embeddings?
  "Database connection timeout" and "DB connect failed" are different strings
  but semantically similar. Embeddings capture this similarity as numbers,
  allowing us to group related logs together even if worded differently.
"""

import numpy as np
from sentence_transformers import SentenceTransformer

# Load a small, fast model (~80MB) — runs on CPU, no GPU needed
_model = SentenceTransformer("all-MiniLM-L6-v2")


def get_embeddings(texts: list[str]) -> np.ndarray:
    """
    Convert a list of text strings into embedding vectors.

    Args:
        texts: list of log messages e.g. ["DB timeout", "Auth failed", ...]

    Returns:
        numpy array of shape (n_texts, 384) — each row is one embedding vector
    """
    if not texts:
        return np.array([])

    # Clean texts — remove empty strings, limit length
    cleaned = [str(t)[:500] for t in texts if t and str(t).strip()]

    if not cleaned:
        return np.array([])

    try:
        embeddings = _model.encode(cleaned, show_progress_bar=False)
        return np.array(embeddings)

    except Exception as e:
        print(f"[embeddings] Error getting embeddings: {e}")
        return np.array([])
