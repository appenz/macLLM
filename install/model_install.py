from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import txtai
from huggingface_hub import snapshot_download

from macllm.core.model_paths import EMBEDDING_MODEL_ID, get_embedding_model_dir


def install_model() -> Path:
    """Download the public embedding model into macLLM's app-managed storage."""
    model_dir = get_embedding_model_dir()
    model_dir.parent.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=EMBEDDING_MODEL_ID,
        local_dir=str(model_dir),
        token=False,
    )
    txtai.Embeddings(path=str(model_dir))
    return model_dir


def uninstall_model() -> Path:
    """Remove only the model snapshot installed by this helper."""
    model_dir = get_embedding_model_dir()
    shutil.rmtree(model_dir, ignore_errors=True)
    return model_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install macLLM local model assets.")
    parser.add_argument(
        "command",
        nargs="?",
        default="install",
        choices=("install", "uninstall"),
        help="Install or uninstall the local embedding model.",
    )
    args = parser.parse_args(argv)

    if args.command == "install":
        model_dir = install_model()
        print(f"Installed {EMBEDDING_MODEL_ID} at {model_dir}")
    else:
        model_dir = uninstall_model()
        print(f"Removed local embedding model from {model_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
