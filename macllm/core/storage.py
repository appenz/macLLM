from pathlib import Path


def get_storage_dir() -> Path:
    path = Path.home() / "Library" / "Application Support" / "macLLM"
    path.mkdir(parents=True, exist_ok=True)
    return path
