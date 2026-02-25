from macllm.tags.base import TagPlugin


class AgentTag(TagPlugin):
    """Handle ``@agent:<name>`` tags to select which agent runs the conversation."""

    def get_prefixes(self):
        return ["@agent:"]

    def expand(self, tag, conversation, request):
        from macllm.agents import AGENT_REGISTRY, _discover_agents
        _discover_agents()

        name = tag[len("@agent:"):]
        if name not in AGENT_REGISTRY:
            known = ", ".join(sorted(AGENT_REGISTRY.keys()))
            print(f"Warning: Unknown agent '{name}'. Available: {known}. Using default.")
            name = "default"

        request.agent_name = name
        return ""

    def supports_autocomplete(self):
        return True

    def autocomplete(self, fragment, max_results=10):
        from macllm.agents import AGENT_REGISTRY, _discover_agents
        _discover_agents()

        prefix = "@agent:"
        if not fragment.startswith(prefix):
            return []

        typed = fragment[len(prefix):]
        matches = [
            f"{prefix}{name}"
            for name in sorted(AGENT_REGISTRY.keys())
            if name.startswith(typed)
        ]
        return matches[:max_results]
