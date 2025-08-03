from Cocoa import NSTextView, NSFont, NSColor, NSAttributedString, NSForegroundColorAttributeName, NSFontAttributeName, NSBackgroundColorAttributeName, NSParagraphStyle, NSMutableParagraphStyle, NSParagraphStyleAttributeName
from AppKit import NSTextAlignmentCenter
from .main_text_helpers import is_markdown

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
        text_storage = text_view.textStorage()
        font = NSFont.systemFontOfSize_(13.0)
        
        # Remove trailing newline to avoid extra blank line after markdown blocks
        text = text.rstrip('\n')
        # Process text line by line
        lines = text.split('\n')
        for i, line in enumerate(lines):
            # Handle headlines
            if line.startswith('#'):
                # Process the entire headline line with bold font
                bold_font = NSFont.boldSystemFontOfSize_(13.0)
                headline_text = line.lstrip('#').strip()
                if i < len(lines) - 1:  # Not the last line
                    headline_text += "\n"
                processed_headline = MainTextHandler._process_bold_text(headline_text, color, bold_font)
                text_storage.appendAttributedString_(processed_headline)
                continue
            
            # Handle bullets
            if line.strip().startswith(('* ', '- ')):
                # Remove the bullet marker and get content
                content = line.strip()[2:]  # Remove first 2 chars (* or - plus space)
                bullet_char = '•'
                
                # Calculate indentation (count leading spaces/tabs)
                indent_level = 0
                for char in line:
                    if char in ' \t':
                        indent_level += 1
                    else:
                        break
                
                # Create indentation
                indent = "  " * indent_level
                
                # Create bullet prefix with indentation
                bullet_prefix = indent + bullet_char + " "
                bullet_prefix_attr = NSAttributedString.alloc().initWithString_attributes_(bullet_prefix, {
                    NSForegroundColorAttributeName: color,
                    NSFontAttributeName: font
                })
                text_storage.appendAttributedString_(bullet_prefix_attr)
                
                # Process and append the bullet content with bold formatting
                processed_content = MainTextHandler._process_bold_text(content, color, font)
                text_storage.appendAttributedString_(processed_content)
                
                # Add newline only if not the last line
                if i < len(lines) - 1:
                    newline_attr = NSAttributedString.alloc().initWithString_("\n")
                    text_storage.appendAttributedString_(newline_attr)
                continue
            
            # Handle regular text with bold formatting
            processed_text = MainTextHandler._process_bold_text(line, color, font)
            text_storage.appendAttributedString_(processed_text)
            
            # Add newline only if not the last line
            if i < len(lines) - 1:
                newline_attr = NSAttributedString.alloc().initWithString_("\n")
                text_storage.appendAttributedString_(newline_attr)
    
    @staticmethod
    def _process_bold_text(text, color, font):
        """Process bold text markers (**text** or __text__) in a line."""
        # Handle **bold** and __bold__ patterns
        import re
        
        # Create a mutable attributed string
        from Foundation import NSMutableAttributedString
        
        # Split text by bold markers
        parts = re.split(r'(\*\*.*?\*\*|__.*?__)', text)
        
        if len(parts) == 1:
            # No bold markers found, return regular text
            attributes = {
                NSForegroundColorAttributeName: color,
                NSFontAttributeName: font
            }
            return NSAttributedString.alloc().initWithString_attributes_(text, attributes)
        
        # Create mutable attributed string
        result = NSMutableAttributedString.alloc().init()
        
        for part in parts:
            if not part:
                continue
                
            # Check if this part is bold (starts and ends with ** or __)
            is_bold = (part.startswith('**') and part.endswith('**')) or \
                     (part.startswith('__') and part.endswith('__'))
            
            if is_bold:
                # Remove the markers and make bold
                bold_text = part[2:-2] if part.startswith('**') else part[2:-2]
                bold_font = NSFont.boldSystemFontOfSize_(13.0)
                attributes = {
                    NSForegroundColorAttributeName: color,
                    NSFontAttributeName: bold_font
                }
            else:
                # Regular text
                attributes = {
                    NSForegroundColorAttributeName: color,
                    NSFontAttributeName: font
                }
                bold_text = part
            
            # Create attributed string for this part
            part_attr = NSAttributedString.alloc().initWithString_attributes_(bold_text, attributes)
            result.appendAttributedString_(part_attr)
        
        return result

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
        
        # Get chat history entries
        chat_history = macllm.chat_history.chat_history
        
        # Define colors for different roles
        user_color = NSColor.blackColor()  # Black
        assistant_color = NSColor.darkGrayColor()  # Dark Grey
        
        # Add each chat entry with appropriate color
        for i, entry in enumerate(chat_history):
            # Track start index to allow highlighting
            start_pos = text_view.textStorage().length()
            role = entry['role']
            text = entry['text']
            
            # Choose color based on role
            if role == 'user':
                color = user_color
                prefix = "User: "
            else:  # assistant
                color = assistant_color
                if is_markdown(text):
                    prefix = None
                else:
                    prefix = "Assistant: "
            

            # Append the colored text
            if prefix:
                MainTextHandler.append_colored_text(text_view, prefix, color)
            
            # Add message content and optional separator + highlight
            if i < len(chat_history) - 1:
                if is_markdown(text):
                    MainTextHandler.append_markdown(text_view, text, color)
                else:
                    MainTextHandler.append_colored_text(text_view, text, color)

                # Apply highlight (exclude upcoming separator)
                end_pos = text_view.textStorage().length()
                if highlight_index is not None and i == highlight_index:
                    highlight_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.9, 0.9, 1.0, 1.0)
                    text_view.textStorage().addAttributes_range_(
                        {NSBackgroundColorAttributeName: highlight_color},
                        (start_pos, end_pos - start_pos)
                    )

                # Add centered separator with paragraph breaks
                separator_text = "\n" + "─"*47 + "\n"
                separator_attributed_text = NSAttributedString.alloc().initWithString_attributes_(separator_text, MainTextHandler._separator_attributes)
                text_view.textStorage().appendAttributedString_(separator_attributed_text)
            else:
                if is_markdown(text):
                    MainTextHandler.append_markdown(text_view, text, color)
                else:
                    MainTextHandler.append_colored_text(text_view, text, color)

                # Apply highlight for the last message
                end_pos = text_view.textStorage().length()
                if highlight_index is not None and i == highlight_index:
                    highlight_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.9, 0.9, 1.0, 1.0)
                    text_view.textStorage().addAttributes_range_(
                        {NSBackgroundColorAttributeName: highlight_color},
                        (start_pos, end_pos - start_pos)
                    )

        
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