from __future__ import annotations

from pathlib import Path

from macllm.core.persistence import get_storage_dir


EMBEDDING_MODEL_ID = "sentence-transformers/all-mpnet-base-v2"
EMBEDDING_MODEL_DIRNAME = Path("models") / "sentence-transformers" / "all-mpnet-base-v2"


def get_embedding_model_dir() -> Path:
    """Return the deterministic app-managed sentence-transformer model path."""
    return get_storage_dir() / EMBEDDING_MODEL_DIRNAME
