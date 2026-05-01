from Cocoa import NSTextView, NSFont, NSColor, NSAttributedString, NSForegroundColorAttributeName, NSFontAttributeName, NSBackgroundColorAttributeName, NSParagraphStyle, NSMutableParagraphStyle, NSParagraphStyleAttributeName
from AppKit import NSTextAlignmentCenter
from macllm.ui.tag_render import render_text_with_pills
from macllm.core.skills import SkillsRegistry

class MainTextHandler:
    """Handles the main text display functionality for the macLLM UI."""
    
    _separator_paragraph_style = None
    _separator_attributes = None
    
    @classmethod
    def _init_separator_attributes(cls):
        if cls._separator_attributes is None:
            cls._separator_paragraph_style = NSMutableParagraphStyle.alloc().init()
            cls._separator_paragraph_style.setAlignment_(NSTextAlignmentCenter)
            
            cls._separator_attributes = {
                NSForegroundColorAttributeName: NSColor.colorWithCalibratedWhite_alpha_(0.9, 1.0),
                NSFontAttributeName: NSFont.systemFontOfSize_(13.0),
                NSParagraphStyleAttributeName: cls._separator_paragraph_style
            }
    
    @staticmethod
    def append_colored_text(text_view, text, color):
        text_storage = text_view.textStorage()
        font = NSFont.systemFontOfSize_(13.0)
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

    _TOOL_DISPLAY = {
        "web_search": lambda args: (
            'Searching the web for "'
            + '", "'.join(str(q) for q in args.get("queries", [])[:3])
            + '"'
        ),
    }

    @staticmethod
    def _render_plan(ts, conversation, muted, light, green, font_sm, font_sm_bold):
        """Render parsed planning checklist and status summary."""
        plan_text = getattr(conversation, "plan_text", None)
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

        status = getattr(conversation, "plan_status", None)
        if status:
            _append("\n", muted)
            _append("Status: ", muted, font_sm_bold)
            status_lines = status.splitlines()
            if status_lines:
                _append(f"{status_lines[0]}\n", light)
                for extra in status_lines[1:]:
                    _append(f"        {extra}\n", light)
        _append("\n", muted)
        return True

    @staticmethod
    def _render_agent_steps(text_view, conversation):
        """Render live agent progress from agent.memory.steps and pending approval."""
        from Foundation import NSMutableAttributedString
        from macllm.ui.approval import ApprovalRenderer
        from smolagents import ActionStep, TaskStep

        ts = text_view.textStorage()

        muted = NSColor.colorWithCalibratedWhite_alpha_(0.50, 1.0)
        light = NSColor.colorWithCalibratedWhite_alpha_(0.62, 1.0)
        green = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.30, 0.69, 0.31, 1.0)
        red   = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.84, 0.24, 0.24, 1.0)

        font_sm      = NSFont.systemFontOfSize_(11.0)
        font_sm_bold = NSFont.boldSystemFontOfSize_(11.0)
        font_mono    = NSFont.monospacedSystemFontOfSize_weight_(10.0, 0.0)

        def _append(text, color, font=font_sm):
            a = NSAttributedString.alloc().initWithString_attributes_(
                text, {NSForegroundColorAttributeName: color, NSFontAttributeName: font})
            ts.appendAttributedString_(a)

        agent = conversation.agent
        if agent is None:
            return

        run_offset = getattr(conversation, '_run_step_offset', 0)
        steps = agent.memory.steps[run_offset:]

        has_tool_calls = any(
            getattr(s, 'tool_calls', None)
            for s in steps if isinstance(s, ActionStep)
        )
        has_live_tool_calls = bool(conversation.tool_calls)
        has_plan = bool(getattr(conversation, "plan_text", None))
        show_steps = has_tool_calls or has_live_tool_calls

        _append("\n\n", muted)

        if has_plan:
            MainTextHandler._render_plan(
                ts, conversation, muted, light, green, font_sm, font_sm_bold
            )

        if show_steps:
            _append("Steps\n", muted, font_sm_bold)
        elif not conversation.pending_approval and not has_plan:
            _append("Thinking...\n", muted, font_sm_bold)

        for step in steps:
            if isinstance(step, ActionStep):
                tool_calls = getattr(step, 'tool_calls', None) or []
                observations = getattr(step, 'observations', None)
                error = getattr(step, 'error', None)

                for tc in tool_calls:
                    name = tc.get('name', 'tool') if isinstance(tc, dict) else getattr(tc, 'name', 'tool')
                    args = tc.get('arguments', {}) if isinstance(tc, dict) else getattr(tc, 'arguments', {})

                    if error:
                        _append("  ✗ ", red, font_sm_bold)
                    elif observations is not None:
                        _append("  ✓ ", green, font_sm_bold)
                    else:
                        _append("  ⟳ ", muted, font_sm_bold)

                    display_fn = MainTextHandler._TOOL_DISPLAY.get(name)
                    if display_fn:
                        _append(f"{display_fn(args)}", light)
                    elif name == "run_command":
                        cmd = args.get('command', '') if isinstance(args, dict) else ''
                        display_cmd = cmd if len(cmd) <= 60 else cmd[:57] + "..."
                        _append(f"{name}", muted)
                        if cmd:
                            _append(f"({display_cmd})", light, font_mono)
                    else:
                        _append(f"{name}", muted)
                        summary = ""
                        if isinstance(args, dict):
                            for k, v in list(args.items())[:2]:
                                sv = str(v)[:40]
                                summary += f"{k}={sv}, "
                            summary = summary.rstrip(", ")
                        if summary:
                            _append(f"({summary})", light)

                    if error:
                        err_str = str(error)[:80]
                        _append(f" — {err_str}", red)
                    _append("\n", muted)

        for tc in conversation.tool_calls:
            _append("  ⟳ ", muted, font_sm_bold)
            _append(f"{tc['message']}\n", light)

        if conversation.pending_approval:
            ApprovalRenderer.render_pending(ts, conversation.pending_approval)

    @staticmethod
    def _render_pending_input(text_view, text):
        """Render queued user input as a dimmed block below agent activity."""
        ts = text_view.textStorage()
        muted = NSColor.colorWithCalibratedWhite_alpha_(0.45, 1.0)
        font = NSFont.systemFontOfSize_(13.0)

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
            text_view.setFont_(NSFont.systemFontOfSize_(13.0))
        
        return MainTextHandler.set_text_content(macllm, text_view)

    @staticmethod
    def set_text_content(macllm, text_view, highlight_index=None):
        from macllm.markdown import reset_code_blocks
        reset_code_blocks()

        MainTextHandler._init_separator_attributes()
        
        text_view.setString_("")
        text_view.setFont_(NSFont.systemFontOfSize_(13.0))
        text_view.setLinkTextAttributes_({})
        
        conv = macllm.chat_history
        messages = conv.get_displayable_messages()
        
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
                font = NSFont.systemFontOfSize_(13.0)
                shortcuts_list = SkillsRegistry.list_manual_commands()
                plugins = getattr(macllm, 'plugins', [])
                attr = render_text_with_pills(text, color, font, shortcuts_list, plugins)
                text_view.textStorage().appendAttributedString_(attr)
            else:
                MainTextHandler.append_markdown(text_view, text, color)

            end_pos = text_view.textStorage().length()
            if highlight_index is not None and i == highlight_index:
                highlight_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.9, 0.9, 1.0, 1.0)
                text_view.textStorage().addAttributes_range_(
                    {NSBackgroundColorAttributeName: highlight_color},
                    (start_pos, end_pos - start_pos)
                )

            if i < len(messages) - 1:
                separator_text = "\n" + "─"*47 + "\n"
                separator_attributed_text = NSAttributedString.alloc().initWithString_attributes_(separator_text, MainTextHandler._separator_attributes)
                text_view.textStorage().appendAttributedString_(separator_attributed_text)

        if conv.is_agent_running() or conv.pending_approval:
            MainTextHandler._render_agent_steps(text_view, conv)

        if conv.pending_input:
            MainTextHandler._render_pending_input(text_view, conv.pending_input)

        layout_manager = text_view.layoutManager()
        text_container = text_view.textContainer()
        
        if layout_manager and text_container:
            glyph_range = layout_manager.glyphRangeForTextContainer_(text_container)
            bounding_rect = layout_manager.boundingRectForGlyphRange_inTextContainer_(glyph_range, text_container)
            return bounding_rect.size.height
        
        return 200.0
