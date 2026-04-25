from macllm.agents.base import MacLLMAgent


class EmailAgent(MacLLMAgent):
    """Managed agent for email operations via the local Superhuman mailbox.

    Read-only access to inbox, sent mail, starred threads, full-text search,
    split inboxes, contacts, and contact profiles.
    Instructions are loaded from ``[agents.email]`` in config.toml.
    """

    macllm_name = "email"
    macllm_description = (
        "Searches, reads, and browses the user's email. Can list inbox, "
        "sent, and starred threads, search by keyword, read full threads, "
        "browse split inboxes, and look up contacts."
    )
    macllm_tools = [
        "get_current_time",
        "email_inbox",
        "email_search",
        "email_read_thread",
        "email_sent",
        "email_starred",
        "email_contacts",
        "email_split_inboxes",
        "email_split_inbox_threads",
        "email_profile",
    ]

    def __init__(self, **kwargs):
        super().__init__(planning_interval=None, **kwargs)
