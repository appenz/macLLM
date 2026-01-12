import os
import pickle
from pathlib import Path


def get_storage_dir() -> Path:
    path = Path.home() / "Library" / "Application Support" / "macLLM"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_latest_path() -> Path:
    return get_storage_dir() / "latest.pkl"


def save_conversation(conversation) -> bool:
    if conversation.agent is None:
        return False
    try:
        data = {
            'steps': conversation.agent.memory.steps,
            'messages': conversation.messages
        }
        with open(get_latest_path(), 'wb') as f:
            pickle.dump(data, f)
        return True
    except Exception:
        return False


def load_conversation(conversation) -> bool:
    path = get_latest_path()
    if not path.exists():
        return False
    if conversation.agent is None:
        return False
    try:
        with open(path, 'rb') as f:
            data = pickle.load(f)
        if isinstance(data, dict):
            conversation.agent.memory.steps = data.get('steps', [])
            conversation.messages = data.get('messages', [])
        else:
            conversation.agent.memory.steps = data
        return True
    except Exception:
        return False


def clear_conversation() -> bool:
    path = get_latest_path()
    if path.exists():
        try:
            path.unlink()
            return True
        except Exception:
            return False
    return True
