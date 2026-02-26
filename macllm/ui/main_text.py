from Cocoa import NSTextView, NSFont, NSColor, NSAttributedString, NSForegroundColorAttributeName, NSFontAttributeName, NSBackgroundColorAttributeName, NSParagraphStyle, NSMutableParagraphStyle, NSParagraphStyleAttributeName
from AppKit import NSTextAlignmentCenter
from macllm.ui.tag_render import render_text_with_pills
from macllm.core.shortcuts import ShortCut

class MainTextHandler:
    """Handles the main text display functionality for the macLLM UI."""
    
    # Static separator attributes - defined once for efficiency
    _separator_paragraph_style = None
    _separator_attributes = None
    
    @classmethod
    def _init_separator_attributes(cls):
        """Initialize static separator attributes if not already done."""
        if cls._separator_attributes is None:
            # Create centered paragraph style for separator
            cls._separator_paragraph_style = NSMutableParagraphStyle.alloc().init()
            cls._separator_paragraph_style.setAlignment_(NSTextAlignmentCenter)
            
            # Define separator attributes
            cls._separator_attributes = {
                NSForegroundColorAttributeName: NSColor.colorWithCalibratedWhite_alpha_(0.9, 1.0),
                NSFontAttributeName: NSFont.systemFontOfSize_(13.0),
                NSParagraphStyleAttributeName: cls._separator_paragraph_style
            }
    
    @staticmethod
    def append_colored_text(text_view, text, color):
        """Append colored text to the NSTextView."""
        # Get the current text storage
        text_storage = text_view.textStorage()
        
        # Create attributed string with the specified color and font
        font = NSFont.systemFontOfSize_(13.0)
        attributes = {
            NSForegroundColorAttributeName: color,
            NSFontAttributeName: font
        }
        attributed_text = NSAttributedString.alloc().initWithString_attributes_(text, attributes)
        
        # Append the attributed text
        text_storage.appendAttributedString_(attributed_text)
    
    @staticmethod
    def append_markdown(text_view, text, color):
        """Append markdown-formatted text to the NSTextView."""
        from macllm.markdown import render_markdown
        attr_str = render_markdown(text, color)
        text_view.textStorage().appendAttributedString_(attr_str)

    @staticmethod
    def _render_agent_status(text_view, status_mgr):
        """Render agent plan and tool calls with rich formatting."""
        from Foundation import NSMutableAttributedString
        ts = text_view.textStorage()

        muted = NSColor.colorWithCalibratedWhite_alpha_(0.50, 1.0)
        light = NSColor.colorWithCalibratedWhite_alpha_(0.62, 1.0)
        green = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.30, 0.69, 0.31, 1.0)
        red   = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.84, 0.24, 0.24, 1.0)

        font_sm      = NSFont.systemFontOfSize_(11.0)
        font_sm_bold = NSFont.boldSystemFontOfSize_(11.0)

        def _append(text, color, font=font_sm):
            a = NSAttributedString.alloc().initWithString_attributes_(
                text, {NSForegroundColorAttributeName: color, NSFontAttributeName: font})
            ts.appendAttributedString_(a)

        _append("\n\n", muted)

        if status_mgr.plan:
            _append("Plan\n", muted, font_sm_bold)
            for line in status_mgr.plan.split('\n'):
                _append(f"  {line}\n", light)

        if status_mgr.tool_calls:
            if status_mgr.plan:
                _append("\n", muted)
            _append("Steps\n", muted, font_sm_bold)
            for entry in status_mgr.tool_calls:
                indent = "  " * (1 + entry.indent)
                if entry.status == "success":
                    _append(f"{indent}✓ ", green, font_sm_bold)
                elif entry.status == "running":
                    _append(f"{indent}⟳ ", muted, font_sm_bold)
                else:
                    _append(f"{indent}✗ ", red, font_sm_bold)
                _append(f"{entry.name}", muted)
                if entry.args_summary:
                    _append(f"({entry.args_summary})", light)
                if entry.status == "error" and entry.result_summary:
                    _append(f" — {entry.result_summary}", red)
                _append("\n", muted)

    @staticmethod
    def calculate_minimum_text_height(macllm):
        """Calculate the minimum height needed to display the initial text content."""
        # If a text area already exists, use it; otherwise create a temporary one for measurement
        if hasattr(macllm.ui, "text_area"):
            text_view = macllm.ui.text_area
        else:
            # Create an off-screen text view with the same width as the real one
            text_corner_radius = macllm.ui.text_corner_radius
            text_area_width = macllm.ui.text_area_width
            text_view = NSTextView.alloc().initWithFrame_(((0, 0), (text_area_width - 2*text_corner_radius, 1000)))
            text_view.setEditable_(False)
            text_view.setDrawsBackground_(False)
            text_view.setFont_(NSFont.systemFontOfSize_(13.0))
        
        # Render the content and get the height
        return MainTextHandler.set_text_content(macllm, text_view)

    @staticmethod
    def set_text_content(macllm, text_view, highlight_index=None):
        """Set the text content for the main text view with colored text for different roles."""
        # Initialize static separator attributes if needed
        MainTextHandler._init_separator_attributes()
        
        # Clear the text view first and set the font
        text_view.setString_("")
        text_view.setFont_(NSFont.systemFontOfSize_(13.0))
        text_view.setLinkTextAttributes_({})
        
        # Get displayable messages (user and assistant only)
        messages = macllm.chat_history.get_displayable_messages()
        
        # Define colors for different roles
        user_color = NSColor.blackColor()  # Black
        assistant_color = NSColor.darkGrayColor()  # Dark Grey
        
        # Add each message with appropriate color
        for i, message in enumerate(messages):
            # Track start index to allow highlighting
            start_pos = text_view.textStorage().length()
            role = message['role']
            text = message['content']
            
            # Choose color based on role
            if role == 'user':
                color = user_color
                prefix = "User: "
            else:  # assistant
                color = assistant_color
                prefix = None

            # Append the colored prefix first (e.g., "User: ")
            if prefix:
                MainTextHandler.append_colored_text(text_view, prefix, color)
            
            # Render message content
            if role == 'user':
                font = NSFont.systemFontOfSize_(13.0)
                shortcuts_list = [s.trigger for s in ShortCut.shortcuts]
                plugins = getattr(macllm, 'plugins', [])
                attr = render_text_with_pills(text, color, font, shortcuts_list, plugins)
                text_view.textStorage().appendAttributedString_(attr)
            else:
                MainTextHandler.append_markdown(text_view, text, color)

            # Apply highlight
            end_pos = text_view.textStorage().length()
            if highlight_index is not None and i == highlight_index:
                highlight_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.9, 0.9, 1.0, 1.0)
                text_view.textStorage().addAttributes_range_(
                    {NSBackgroundColorAttributeName: highlight_color},
                    (start_pos, end_pos - start_pos)
                )

            # Add separator between messages (not after the last one)
            if i < len(messages) - 1:
                separator_text = "\n" + "─"*47 + "\n"
                separator_attributed_text = NSAttributedString.alloc().initWithString_attributes_(separator_text, MainTextHandler._separator_attributes)
                text_view.textStorage().appendAttributedString_(separator_attributed_text)

        # Add agent status if present (shown at bottom during agent execution)
        from macllm.macllm import MacLLM
        status_mgr = MacLLM.get_status_manager()
        if status_mgr.plan or status_mgr.tool_calls:
            MainTextHandler._render_agent_status(text_view, status_mgr)
        
        # Calculate height from the rendered content
        layout_manager = text_view.layoutManager()
        text_container = text_view.textContainer()
        
        if layout_manager and text_container:
            # Get the glyph range for the entire text
            glyph_range = layout_manager.glyphRangeForTextContainer_(text_container)
            
            # Calculate the bounding rect for the glyphs with width constraints
            bounding_rect = layout_manager.boundingRectForGlyphRange_inTextContainer_(glyph_range, text_container)
            return bounding_rect.size.height
        
        # Fallback to a reasonable minimum height
        return 200.0 