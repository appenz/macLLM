from macllm.agents.base import MacLLMAgent
from macllm.tools.filesystem import FILESYSTEM_TOOLS


class EmailAgent(MacLLMAgent):
    """Managed agent for email operations via the local Superhuman mailbox.

    Read-only access to inbox, sent mail, starred threads, full-text search,
    split inboxes, contacts, and contact profiles.
    Instructions are loaded from ``[agents.email]`` in config.toml.
    """

    macllm_name = "email"
    read_only_no_hostfs = True
    macllm_description = (
        "Searches, reads, and browses the user's email. Can list inbox, "
        "sent, and starred threads, search by keyword, read full threads, "
        "browse split inboxes, and look up contacts."
    )
    macllm_tools = [
        *FILESYSTEM_TOOLS,
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
