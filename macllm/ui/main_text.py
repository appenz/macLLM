from Cocoa import NSTextView, NSFont, NSColor, NSAttributedString, NSForegroundColorAttributeName, NSFontAttributeName, NSBackgroundColorAttributeName, NSParagraphStyle, NSMutableParagraphStyle, NSParagraphStyleAttributeName
from AppKit import NSTextAlignmentCenter
from macllm.ui.tag_render import render_text_with_pills
from macllm.markdown.blocks import FONT_SIZE
from macllm.core.skills import SkillsRegistry
from macllm.core.conversation_log import messages_from_log
from macllm.ui.agent_activity import active_plan, project_activity, without_update

class MainTextHandler:
    """Handles the main text display functionality for the macLLM UI."""
    
    _separator_paragraph_style = None
    _separator_attributes = None
    _last_highlight_range = None
    _message_ranges = []
    
    @classmethod
    def _init_separator_attributes(cls):
        if cls._separator_attributes is None:
            cls._separator_paragraph_style = NSMutableParagraphStyle.alloc().init()
            cls._separator_paragraph_style.setAlignment_(NSTextAlignmentCenter)
            
            cls._separator_attributes = {
                NSForegroundColorAttributeName: NSColor.colorWithCalibratedWhite_alpha_(0.9, 1.0),
                NSFontAttributeName: NSFont.systemFontOfSize_(FONT_SIZE),
                NSParagraphStyleAttributeName: cls._separator_paragraph_style
            }
    
    @staticmethod
    def append_colored_text(text_view, text, color):
        text_storage = text_view.textStorage()
        font = NSFont.systemFontOfSize_(FONT_SIZE)
        attributes = {
            NSForegroundColorAttributeName: color,
            NSFontAttributeName: font
        }
        attributed_text = NSAttributedString.alloc().initWithString_attributes_(text, attributes)
        text_storage.appendAttributedString_(attributed_text)
    
    @staticmethod
    def append_markdown(text_view, text, color):
        from macllm.markdown import render_markdown, get_last_render_block_infos, add_code_block_range
        base = text_view.textStorage().length()
        attr_str = render_markdown(text, color)
        text_view.textStorage().appendAttributedString_(attr_str)
        for block_id, rel_start, length in get_last_render_block_infos():
            add_code_block_range(block_id, base + rel_start, length)

    @staticmethod
    def displayable_messages(conversation):
        return [
            m for m in messages_from_log(conversation.conversation_log)
            if m["role"] in ("user", "assistant")
        ]

    @staticmethod
    def _render_plan(ts, conversation, muted, light, green, font_sm, font_sm_bold):
        """Render the active run's parsed planning checklist."""
        plan = active_plan(conversation.conversation_log)
        plan_text = without_update(plan.get("text", "")) if plan else None
        if not plan_text:
            return False

        def _append(text, color, font=font_sm):
            a = NSAttributedString.alloc().initWithString_attributes_(
                text, {NSForegroundColorAttributeName: color, NSFontAttributeName: font})
            ts.appendAttributedString_(a)

        _append("Plan\n", muted, font_sm_bold)
        for line in plan_text.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("[x]"):
                color = green
            elif stripped.startswith("[~]"):
                color = muted
            elif stripped.startswith("[ ]"):
                color = light
            else:
                color = light
            _append(f"  {line}\n", color)

        _append("\n", muted)
        return True

    @staticmethod
    def _render_agent_activity(text_view, conversation):
        """Render the active run as a passive projection of conversation facts."""
        from macllm.ui.approval import ApprovalRenderer

        ts = text_view.textStorage()

        muted = NSColor.colorWithCalibratedWhite_alpha_(0.50, 1.0)
        light = NSColor.colorWithCalibratedWhite_alpha_(0.62, 1.0)
        green = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.30, 0.69, 0.31, 1.0)

        font_sm      = NSFont.systemFontOfSize_(11.0)
        font_sm_bold = NSFont.boldSystemFontOfSize_(11.0)
        font_mono    = NSFont.monospacedSystemFontOfSize_weight_(10.0, 0.0)
        update_style = NSMutableParagraphStyle.alloc().init()
        update_style.setParagraphSpacing_(3.3)

        def _append(text, color, font=font_sm, style=None):
            attrs = {NSForegroundColorAttributeName: color, NSFontAttributeName: font}
            if style:
                attrs[NSParagraphStyleAttributeName] = style
            a = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
            ts.appendAttributedString_(a)

        agent = conversation.agent
        if agent is None:
            return

        _append("\n\n", muted)
        MainTextHandler._render_plan(
            ts, conversation, muted, light, green, font_sm, font_sm_bold
        )

        parent_name = getattr(agent, "macllm_name", None) or getattr(agent, "name", "")
        updates, current = project_activity(conversation.conversation_log, parent_name)
        for update in updates:
            _append(f"{update}\n", light, style=update_style)

        if current:
            kind, value = current
            if kind == "planning":
                _append("Planning...\n", muted, font_sm_bold)
            elif kind == "update":
                _append(f"{value}\n", light, style=update_style)
            elif kind == "subagent":
                _append(f"Invoking {value} subagent...\n", muted, font_sm_bold)
            elif kind == "tool":
                font = font_mono if value.get("tool") == "run_command" else font_sm
                _append(f"{value.get('message') or value.get('tool', 'Using tool')}\n", light, font)

        if conversation.pending_approval:
            ApprovalRenderer.render_pending(ts, conversation.pending_approval)

    @staticmethod
    def _render_pending_input(text_view, text):
        """Render queued user input as a dimmed block below agent activity."""
        ts = text_view.textStorage()
        muted = NSColor.colorWithCalibratedWhite_alpha_(0.45, 1.0)
        font = NSFont.systemFontOfSize_(FONT_SIZE)

        def _append(s, color, f=font):
            a = NSAttributedString.alloc().initWithString_attributes_(
                s, {NSForegroundColorAttributeName: color, NSFontAttributeName: f})
            ts.appendAttributedString_(a)

        _append("\n", muted)
        _append("Pending: ", muted, NSFont.boldSystemFontOfSize_(11.0))
        _append(text + "\n", muted)

    @staticmethod
    def calculate_minimum_text_height(macllm):
        if hasattr(macllm.ui, "text_area"):
            text_view = macllm.ui.text_area
        else:
            text_corner_radius = macllm.ui.text_corner_radius
            text_area_width = macllm.ui.text_area_width
            text_view = NSTextView.alloc().initWithFrame_(((0, 0), (text_area_width - 2*text_corner_radius, 1000)))
            text_view.setEditable_(False)
            text_view.setDrawsBackground_(False)
            text_view.setFont_(NSFont.systemFontOfSize_(FONT_SIZE))
        
        return MainTextHandler.set_text_content(macllm, text_view)

    @staticmethod
    def set_text_content(macllm, text_view, highlight_index=None):
        from macllm.markdown import reset_code_blocks
        reset_code_blocks()
        MainTextHandler._last_highlight_range = None
        MainTextHandler._message_ranges = []

        MainTextHandler._init_separator_attributes()
        
        text_view.setString_("")
        text_view.setFont_(NSFont.systemFontOfSize_(FONT_SIZE))
        text_view.setLinkTextAttributes_({})
        
        conv = macllm.chat_history
        messages = MainTextHandler.displayable_messages(conv)
        
        user_color = NSColor.blackColor()
        assistant_color = NSColor.darkGrayColor()
        
        for i, message in enumerate(messages):
            start_pos = text_view.textStorage().length()
            role = message['role']
            text = message['content']
            
            if role == 'user':
                color = user_color
                prefix = "User: "
            else:
                color = assistant_color
                prefix = None

            if prefix:
                MainTextHandler.append_colored_text(text_view, prefix, color)
            
            if role == 'user':
                font = NSFont.systemFontOfSize_(FONT_SIZE)
                shortcuts_list = SkillsRegistry.list_manual_commands()
                plugins = getattr(macllm, 'plugins', [])
                attr = render_text_with_pills(text, color, font, shortcuts_list, plugins)
                text_view.textStorage().appendAttributedString_(attr)
            else:
                MainTextHandler.append_markdown(text_view, text, color)

            end_pos = text_view.textStorage().length()
            MainTextHandler._message_ranges.append((start_pos, end_pos - start_pos))
            if highlight_index is not None and i == highlight_index:
                highlight_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.9, 0.9, 1.0, 1.0)
                MainTextHandler._last_highlight_range = (start_pos, end_pos - start_pos)
                text_view.textStorage().addAttributes_range_(
                    {NSBackgroundColorAttributeName: highlight_color},
                    (start_pos, end_pos - start_pos)
                )

            if i < len(messages) - 1:
                separator_text = "\n" + "─"*47 + "\n"
                separator_attributed_text = NSAttributedString.alloc().initWithString_attributes_(separator_text, MainTextHandler._separator_attributes)
                text_view.textStorage().appendAttributedString_(separator_attributed_text)

        if ((conv.is_agent_running() and not conv.abort_event.is_set())
                or conv.pending_approval):
            MainTextHandler._render_agent_activity(text_view, conv)

        if conv.pending_input:
            MainTextHandler._render_pending_input(text_view, conv.pending_input)

        layout_manager = text_view.layoutManager()
        text_container = text_view.textContainer()
        
        if layout_manager and text_container:
            glyph_range = layout_manager.glyphRangeForTextContainer_(text_container)
            bounding_rect = layout_manager.boundingRectForGlyphRange_inTextContainer_(glyph_range, text_container)
            return bounding_rect.size.height
        
        return 200.0
