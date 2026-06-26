"""Tag plugin for /reload command.

Reloads merged config, models, skills, and index directories — the same
work that the old ``MacLLM.handle_instructions("/reload")`` special-case did,
but executed during the normal tag-expansion phase so it happens before the
agent is invoked.
"""

from macllm.tags.base import TagPlugin


class CommandTag(TagPlugin):
    """Handle the ``/reload`` command as a tag plugin."""

    PREFIX_RELOAD = "/reload"

    def get_prefixes(self):
        return [self.PREFIX_RELOAD]

    def expand(self, tag, conversation, request):
        if tag == self.PREFIX_RELOAD:
            return self._do_reload(conversation)
        return ""

    def _do_reload(self, conversation):
        from macllm.core.config import load_runtime_config
        from macllm.core.llm_service import refresh_models
        from macllm.core.skills import SkillsRegistry

        app = self.macllm
        app.config = load_runtime_config()
        refresh_models()
        summary = SkillsRegistry.reload()
        app._apply_index_dirs_from_config()
        try:
            from macllm.tags.file_tag import FileTag
            FileTag._start_reindex()
        except Exception:
            pass

        conversation.add_user_message("/reload")
        conversation.add_assistant_message(summary)
        conversation._notify_ui()

        from macllm.core.persistence import save_all_conversations
        if not app.ephemeral:
            save_all_conversations(app.conversation_history)

        request.expanded_prompt = ""
        return ""
