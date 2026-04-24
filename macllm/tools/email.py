"""Email tools: read-only access to the local Superhuman mailbox via shmail."""

from __future__ import annotations

from macllm.tools._debug import macllm_tool, set_tool_message


def _mailbox():
    from shmail import Mailbox

    return Mailbox()


def _fmt_address(addr) -> str:
    return f"{addr.name} <{addr.email}>" if addr.name else addr.email


def _fmt_addresses(addrs) -> str:
    return ", ".join(_fmt_address(a) for a in addrs)


def _fmt_thread_summary(t) -> str:
    parts = [
        f"ID: {t.short_id}",
        f"Subject: {t.subject}",
        f"Messages: {t.message_count}",
    ]
    if t.latest_date:
        parts.append(f"Date: {t.latest_date:%Y-%m-%d %H:%M}")
    participants = _fmt_addresses(t.participants)
    if participants:
        parts.append(f"Participants: {participants}")
    if t.has_attachments:
        parts.append("Has attachments: yes")
    labels = [l for l in t.label_ids if l not in ("INBOX", "SENT", "IMPORTANT")]
    if labels:
        parts.append(f"Labels: {', '.join(labels)}")
    return "\n".join(parts)


def _fmt_message(msg) -> str:
    parts = [
        f"From: {_fmt_address(msg.sender)}",
        f"To: {_fmt_addresses(msg.to)}",
    ]
    if msg.cc:
        parts.append(f"CC: {_fmt_addresses(msg.cc)}")
    parts.append(f"Date: {msg.date:%Y-%m-%d %H:%M}")
    parts.append(f"Subject: {msg.subject}")
    if msg.attachments:
        att_list = ", ".join(f"{a.name} ({a.type})" for a in msg.attachments)
        parts.append(f"Attachments: {att_list}")
    parts.append(f"\n{msg.snippet}")
    return "\n".join(parts)


@macllm_tool
def email_inbox(limit: str = "20") -> str:
    """
    List recent inbox threads from the user's email.

    Args:
        limit: Maximum number of threads to return (default 20, max 50).

    Returns:
        Formatted list of recent inbox threads with ID, subject, date, and participants.
    """
    n = min(int(limit), 50)
    set_tool_message(f"Loading inbox (up to {n})")
    try:
        with _mailbox() as mb:
            threads = mb.inbox(n)
    except Exception as e:
        return f"Error reading inbox: {e}"

    if not threads:
        return "Inbox is empty."
    return "\n\n---\n\n".join(_fmt_thread_summary(t) for t in threads)


@macllm_tool
def email_search(query: str, limit: str = "20") -> str:
    """
    Search email threads by keyword or query string.
    Supports full-text search with Porter stemming. You can also use
    prefix filters like "from:name@example.com" or "subject:quarterly".

    Args:
        query: The search query (keywords, sender, subject, etc.).
        limit: Maximum number of results (default 20, max 50).

    Returns:
        Formatted list of matching threads.
    """
    n = min(int(limit), 50)
    set_tool_message(f'Searching email for "{query}"')
    try:
        with _mailbox() as mb:
            threads = mb.search(query, limit=n)
    except Exception as e:
        return f"Error searching email: {e}"

    if not threads:
        return f"No threads found for query: {query}"
    return "\n\n---\n\n".join(_fmt_thread_summary(t) for t in threads)


@macllm_tool
def email_read_thread(thread_id: str) -> str:
    """
    Read the full content of an email thread by its ID (or ID prefix).
    Use this after finding a thread via email_inbox or email_search
    to see the full message contents.

    Args:
        thread_id: The thread ID or short ID prefix (e.g. "19db387d").

    Returns:
        Full thread with all messages, senders, dates, and snippets.
    """
    set_tool_message(f"Reading thread {thread_id}")
    try:
        with _mailbox() as mb:
            thread = mb.thread(thread_id.strip())
    except Exception as e:
        return f"Error reading thread: {e}"

    if thread is None:
        return f"No thread found with ID: {thread_id}"

    header = f"Thread: {thread.subject}\nID: {thread.id}\nMessages: {thread.message_count}"
    messages = "\n\n---\n\n".join(_fmt_message(m) for m in thread.messages)
    return f"{header}\n\n{messages}"


@macllm_tool
def email_sent(limit: str = "20") -> str:
    """
    List recent sent email threads.

    Args:
        limit: Maximum number of threads to return (default 20, max 50).

    Returns:
        Formatted list of recent sent threads.
    """
    n = min(int(limit), 50)
    set_tool_message("Loading sent mail")
    try:
        with _mailbox() as mb:
            threads = mb.sent(n)
    except Exception as e:
        return f"Error reading sent mail: {e}"

    if not threads:
        return "No sent threads found."
    return "\n\n---\n\n".join(_fmt_thread_summary(t) for t in threads)


@macllm_tool
def email_starred(limit: str = "20") -> str:
    """
    List starred/flagged email threads.

    Args:
        limit: Maximum number of threads to return (default 20, max 50).

    Returns:
        Formatted list of starred threads.
    """
    n = min(int(limit), 50)
    set_tool_message("Loading starred mail")
    try:
        with _mailbox() as mb:
            threads = mb.starred(n)
    except Exception as e:
        return f"Error reading starred mail: {e}"

    if not threads:
        return "No starred threads found."
    return "\n\n---\n\n".join(_fmt_thread_summary(t) for t in threads)


@macllm_tool
def email_contacts(query: str = "", limit: str = "30") -> str:
    """
    List or search email contacts. Without a query, returns top contacts
    by frequency. With a query, searches by name or email address.

    Args:
        query: Optional name or email to search for. Leave empty for top contacts.
        limit: Maximum number of contacts to return (default 30, max 100).

    Returns:
        Formatted list of contacts with name, email, and frequency score.
    """
    n = min(int(limit), 100)
    set_tool_message(f'Searching contacts for "{query}"' if query.strip() else "Listing contacts")
    try:
        with _mailbox() as mb:
            if query.strip():
                contacts = mb.contact_search(query.strip())[:n]
            else:
                contacts = mb.contacts(limit=n)
    except Exception as e:
        return f"Error reading contacts: {e}"

    if not contacts:
        return "No contacts found." if query else "Contact list is empty."

    lines = []
    for c in contacts:
        entry = f"{c.name} <{c.email}>" if c.name else c.email
        if c.score:
            entry += f" (score: {c.score:.1f})"
        lines.append(entry)
    return "\n".join(lines)


@macllm_tool
def email_split_inboxes() -> str:
    """
    List all split inbox definitions (Superhuman split inboxes).

    Returns:
        Formatted list of split inboxes with name, type, and status.
    """
    set_tool_message("Loading split inboxes")
    try:
        with _mailbox() as mb:
            splits = mb.split_inboxes
    except Exception as e:
        return f"Error reading split inboxes: {e}"

    if not splits:
        return "No split inboxes configured."

    lines = []
    for s in splits:
        status = " (disabled)" if s.is_disabled else ""
        lines.append(f"{s.name} [{s.type}]{status} — ID: {s.id}")
    return "\n".join(lines)


@macllm_tool
def email_split_inbox_threads(split_id: str, limit: str = "20") -> str:
    """
    List recent threads from a specific split inbox.
    Use email_split_inboxes first to find available split inbox IDs.

    Args:
        split_id: The split inbox ID (e.g. "SH_SPLIT_INBOX_16861807552321").
        limit: Maximum number of threads to return (default 20, max 50).

    Returns:
        Formatted list of threads in the split inbox.
    """
    n = min(int(limit), 50)
    set_tool_message(f"Loading split inbox {split_id}")
    try:
        with _mailbox() as mb:
            threads = mb.split_inbox_threads(split_id.strip(), limit=n)
    except Exception as e:
        return f"Error reading split inbox: {e}"

    if not threads:
        return f"No threads found in split inbox: {split_id}"
    return "\n\n---\n\n".join(_fmt_thread_summary(t) for t in threads)


@macllm_tool
def email_profile(email_address: str) -> str:
    """
    Look up a contact's enrichment profile (name, bio, location, timezone).

    Args:
        email_address: The email address to look up.

    Returns:
        Profile information if available, or a not-found message.
    """
    set_tool_message(f"Looking up {email_address}")
    try:
        with _mailbox() as mb:
            profile = mb.profile(email_address.strip())
    except Exception as e:
        return f"Error looking up profile: {e}"

    if profile is None:
        return f"No profile found for {email_address}"

    parts = [f"Email: {profile.email}"]
    if profile.name:
        parts.append(f"Name: {profile.name}")
    if profile.bio:
        parts.append(f"Bio: {profile.bio}")
    if profile.location:
        parts.append(f"Location: {profile.location}")
    if profile.timezone:
        parts.append(f"Timezone: {profile.timezone}")
    return "\n".join(parts)
