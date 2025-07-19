from Cocoa import NSTextView, NSFont, NSColor, NSAttributedString, NSForegroundColorAttributeName, NSFontAttributeName, NSParagraphStyle, NSMutableParagraphStyle, NSParagraphStyleAttributeName
from AppKit import NSTextAlignmentCenter

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
    def calculate_minimum_text_height(macllm):
        """Calculate the minimum height needed to display the initial text content."""
        # Generate main text from chat history
        main_text = macllm.chat_history.get_chat_history_original()
        
        text_area_width = macllm.ui.text_area_width
        text_corner_radius = macllm.ui.text_corner_radius
        # Create a temporary NSTextView with the same width as our intended text area
        temp_text_view = NSTextView.alloc().initWithFrame_(((0, 0), (text_area_width - 2*text_corner_radius, 1000)))
        
        # Set the same font and text content
        temp_text_view.setFont_(NSFont.systemFontOfSize_(13.0))
        temp_text_view.setString_(main_text)

        # Get the layout manager to calculate the actual height with width constraints
        layout_manager = temp_text_view.layoutManager()
        text_container = temp_text_view.textContainer()
        
        if layout_manager and text_container:
            # Get the glyph range for the entire text
            glyph_range = layout_manager.glyphRangeForTextContainer_(text_container)
            
            # Calculate the bounding rect for the glyphs with width constraints
            bounding_rect = layout_manager.boundingRectForGlyphRange_inTextContainer_(glyph_range, text_container)
            return bounding_rect.size.height
        
        # Fallback to a reasonable minimum height
        return 200.0

    @staticmethod
    def set_text_content(macllm, text_view):
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
            role = entry['role']
            text = entry['text']
            
            # Choose color based on role
            if role == 'user':
                color = user_color
                prefix = "User: "
            else:  # assistant
                color = assistant_color
                prefix = "Assistant: "
            
            # Append the colored text
            MainTextHandler.append_colored_text(text_view, prefix, color)
            
            # Add separator between messages, but not after the last one
            if i < len(chat_history) - 1:
                MainTextHandler.append_colored_text(text_view, text, color)
                
                # Add centered separator with paragraph breaks
                separator_text = "\n" + "─"*47 + "\n"
                separator_attributed_text = NSAttributedString.alloc().initWithString_attributes_(separator_text, MainTextHandler._separator_attributes)
                text_view.textStorage().appendAttributedString_(separator_attributed_text)
            else:
                MainTextHandler.append_colored_text(text_view, text, color) 