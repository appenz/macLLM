import os
import pickle
import threading
from pathlib import Path

from macllm.agents import get_agent_class
from macllm.core.chat_history import Conversation
from macllm.core.context import register_conversation
from macllm.core.conversation_log import log_from_messages, persistable_log
from macllm.core.storage import get_storage_dir

_save_lock = threading.Lock()

def get_latest_path() -> Path:
    return get_storage_dir() / "latest.pkl"


def get_conversations_path() -> Path:
    return get_storage_dir() / "conversations.pkl"


def _conversation_log(conversation):
    log = getattr(conversation, 'conversation_log', None)
    if isinstance(log, list) and log:
        return persistable_log(log)
    messages = getattr(conversation, 'messages', [])
    return log_from_messages(messages if isinstance(messages, list) else [])


# ---------------------------------------------------------------------------
# Single-conversation persistence (kept for backward compat / migration)
# ---------------------------------------------------------------------------
def save_conversation(conversation) -> bool:
    if conversation.agent is None:
        return False
    conv_id = conversation.conv_id
    try:
        data = {
            'conv_id': conv_id,
            'steps': conversation.agent.memory.steps,
            'conversation_log': _conversation_log(conversation),
            'agent_name': getattr(conversation.agent, 'macllm_name', 'default'),
            'speed_level': getattr(conversation, 'speed_level', 'normal'),
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
        if not isinstance(data, dict):
            raise TypeError("Saved conversation must be a dictionary.")
        conversation.conv_id = data['conv_id']
        agent_name = data['agent_name']
        conversation.speed_level = data['speed_level']
        conversation.agent_cls = get_agent_class(agent_name)
        conversation._create_agent()
        conversation.agent.memory.steps = data['steps']
        conversation.conversation_log = data['conversation_log']
        return True
    except KeyError:
        raise
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


# ---------------------------------------------------------------------------
# Multi-conversation persistence
# ---------------------------------------------------------------------------
def _serialize_conversation(conversation) -> dict | None:
    """Serialize a single Conversation to a plain dict."""
    if conversation.agent is None:
        return None
    conv_id = conversation.conv_id
    try:
        return {
            'conv_id': conv_id,
            'steps': conversation.agent.memory.steps,
            'conversation_log': _conversation_log(conversation),
            'agent_name': getattr(conversation.agent, 'macllm_name', 'default'),
            'speed_level': getattr(conversation, 'speed_level', 'normal'),
            'title': getattr(conversation, 'title', 'New'),
        }
    except Exception:
        return None


def save_all_conversations(conversation_history) -> bool:
    """Persist every conversation in *conversation_history* to disk.

    Thread-safe: multiple agent threads may trigger saves concurrently.
    """
    with _save_lock:
        try:
            entries = []
            for conv in conversation_history.conversations:
                entry = _serialize_conversation(conv)
                if entry is not None:
                    entries.append(entry)
            data = {
                'conversations': entries,
                'active_index': conversation_history.active_index,
            }
            with open(get_conversations_path(), 'wb') as f:
                pickle.dump(data, f)
            return True
        except Exception:
            return False


def load_all_conversations(conversation_history) -> bool:
    """Restore conversations from disk into *conversation_history*.

    Falls back to migrating the legacy single-conversation file if the
    multi-conversation file doesn't exist yet.
    """
    path = get_conversations_path()

    # Migration path: legacy latest.pkl -> single conversation
    if not path.exists():
        legacy = get_latest_path()
        if not legacy.exists():
            return False
        conv = conversation_history.get_current_conversation()
        if conv is None:
            conv = conversation_history.add_conversation()
        ok = load_conversation(conv)
        if ok:
            conv.title = "Restored"
        return ok

    try:
        with open(path, 'rb') as f:
            data = pickle.load(f)

        entries = data['conversations']
        if not entries:
            return False

        conversation_history.conversations.clear()
        conversation_history.active_index = -1

        for entry in entries:
            conv = Conversation()
            conv.conv_id = entry['conv_id']
            agent_name = entry['agent_name']
            conv.speed_level = entry['speed_level']
            conv.agent_cls = get_agent_class(agent_name)
            conv._create_agent()
            conv.agent.memory.steps = entry['steps']
            conv.conversation_log = entry['conversation_log']
            conv.title = entry['title']
            register_conversation(conv)
            conversation_history.conversations.append(conv)

        saved_index = data['active_index']
        conversation_history.active_index = max(0, min(saved_index, len(entries) - 1))
        return True
    except KeyError:
        raise
    except Exception:
        return False
