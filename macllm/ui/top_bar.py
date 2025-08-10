from Cocoa import (
    NSBox,
    NSBoxCustom,
    NSNoBorder,
    NSImageView,
    NSTextView,
    NSFont,
    NSColor,
    NSMutableParagraphStyle,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSParagraphStyleAttributeName,
    NSAttributedString,
)
from AppKit import NSLineBorder
from Quartz import CGColorCreateGenericRGB

# Helper function to convert NSColor to CGColor
def _cgcolor_from_nscolor(nscolor):
    rgb = nscolor.colorUsingColorSpaceName_("NSCalibratedRGBColorSpace")
    return CGColorCreateGenericRGB(rgb.redComponent(), rgb.greenComponent(), rgb.blueComponent(), rgb.alphaComponent())

# Main Handler for the top bar that renders the logo, context and statistics
class TopBarHandler:

    @staticmethod
    def render_context_items(macllm_ui, parent_view, origin_x: int, origin_y: int, height: int, available_width: int):
        """Render the context items strip using the first actual context entry if available."""
        # Remove any existing context pills from previous renders
        if hasattr(macllm_ui, "context_pills"):
            for pill in macllm_ui.context_pills:
                pill.removeFromSuperview()
        
        # Try to read the first non-image context entry from chat history
        pill = None
        try:
            conversation = getattr(macllm_ui.macllm, "chat_history", None)
            context_items = getattr(conversation, "context_history", []) if conversation else []
            first_entry = None
            for ctx in context_items:
                if ctx.get("type") == "image":
                    continue
                content = ctx.get("context")
                if isinstance(content, str) and content:
                    first_entry = ctx
                    break

            if first_entry is not None:
                pill_width = 120
                pill = TopBarHandler.render_context_block(
                    macllm_ui=macllm_ui,
                    parent_view=parent_view,
                    x=origin_x,
                    y=origin_y,
                    width=pill_width,
                    height=height,
                    context_entry=first_entry,
                )
        except Exception:
            pill = None

        # Keep track of pills for cleanup next time (empty if nothing rendered)
        macllm_ui.context_pills = [pill] if pill is not None else []

    @staticmethod
    def render_context_block(macllm_ui, parent_view, x: int, y: int, width: int, height: int, context_entry: dict):
        """Render a single context pill at x with given width using context_entry (name, type, context)."""
        pill = NSBox.alloc().initWithFrame_(((x, y), (width, height)))
        pill.setBoxType_(NSBoxCustom)
        # Use CALayer-backed border for reliable rounded pill borders
        pill.setBorderType_(NSNoBorder)
        pill.setCornerRadius_(macllm_ui.context_pill_corner_radius)
        pill.setFillColor_(macllm_ui.context_bg_color)
        pill.setWantsLayer_(True)
        if pill.layer() is not None:
            pill.layer().setCornerRadius_(macllm_ui.context_pill_corner_radius)
            pill.layer().setBorderWidth_(1.0)
            pill.layer().setBorderColor_(_cgcolor_from_nscolor(macllm_ui.darker_grey))
            pill.layer().setBackgroundColor_(_cgcolor_from_nscolor(macllm_ui.context_bg_color))
        parent_view.addSubview_(pill)
        
        # Render text content inside the pill with clipping
        text = context_entry.get("context", "")
        if text:
            # Add some padding inside the pill
            padding = 6
            text_view = NSTextView.alloc().initWithFrame_(((0, -3), (width - 2*padding, height - 2*padding)))
            text_view.setEditable_(False)
            text_view.setSelectable_(False)
            text_view.setDrawsBackground_(False)
            text_view.setTextContainerInset_((0.0, 0.0))
            
            # Disable text wrapping and scrolling for clipping effect
            if text_view.textContainer() is not None:
                text_view.textContainer().setContainerSize_((width, height))
                text_view.textContainer().setWidthTracksTextView_(False)
                text_view.textContainer().setHeightTracksTextView_(False)
                text_view.textContainer().setLineFragmentPadding_(0.0)
            
            # Set 13pt font with normal text color
            attrs = {
                NSFontAttributeName: NSFont.systemFontOfSize_(9.0),
                NSForegroundColorAttributeName: NSColor.blackColor(),
            }

            # Remove blank lines from text, we want to show the user as much ass possible in the small amount of space we have
            text = "\n".join([line for line in text.split("\n") if line.strip()])

            # Display name is: icon + "@" + reference name
            text = f"{context_entry.get('icon', '')} @{context_entry.get('name', '')}\n"+text

            attr_str = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
            text_view.textStorage().setAttributedString_(attr_str)
            
            # Enable clipping to pill bounds
            text_view.setClipsToBounds_(True)
            pill.addSubview_(text_view)
        
        return pill

    @staticmethod
    def create_or_update_top_bar(macllm_ui, parent_view, top_bar_y: int):
        text_corner_radius = macllm_ui.text_corner_radius
        # Create/update container
        if not hasattr(macllm_ui, "top_bar_container"):
            top_bar_container = NSBox.alloc().initWithFrame_(
                ((macllm_ui.text_area_x, top_bar_y), (macllm_ui.text_area_width, macllm_ui.top_bar_height))
            )
            top_bar_container.setBoxType_(NSBoxCustom)
            top_bar_container.setBorderType_(NSNoBorder)
            top_bar_container.setCornerRadius_(text_corner_radius)
            top_bar_container.setFillColor_(macllm_ui.dark_grey)
            parent_view.addSubview_(top_bar_container)
            macllm_ui.top_bar_container = top_bar_container
        else:
            top_bar_container = macllm_ui.top_bar_container
            top_bar_container.setFrame_(((macllm_ui.text_area_x, top_bar_y), (macllm_ui.text_area_width, macllm_ui.top_bar_height)))

        # Layout within top bar
        top_bar_internal_padding = 8
        icon_x_internal = 0
        # Align elements consistently with previous layout
        icon_y = int((macllm_ui.top_bar_height - macllm_ui.icon_width) / 2) - 5
        text_y = icon_y
        text_height = macllm_ui.top_bar_height - text_y - 10

        context_area_x = icon_x_internal + macllm_ui.icon_width + top_bar_internal_padding
        text_field_x = macllm_ui.text_area_width - macllm_ui.top_bar_text_field_width - top_bar_internal_padding
        context_available_width = max(0, text_field_x - context_area_x)

        # Logo image view
        if not hasattr(macllm_ui, "logo_image_view"):
            image_view = NSImageView.alloc().initWithFrame_(((icon_x_internal, icon_y), (macllm_ui.icon_width, macllm_ui.icon_width)))
            image_view.setImage_(macllm_ui.logo_image)
            image_view.setImageScaling_(3)
            image_view.setImageAlignment_(1)
            image_view.setImageFrameStyle_(0)
            image_view.setAnimates_(False)
            image_view.setContentHuggingPriority_forOrientation_(1000, 0)
            image_view.setContentHuggingPriority_forOrientation_(1000, 1)
            top_bar_container.addSubview_(image_view)
            macllm_ui.logo_image_view = image_view
        else:
            image_view = macllm_ui.logo_image_view
            image_view.setFrame_(((icon_x_internal, icon_y), (macllm_ui.icon_width, macllm_ui.icon_width)))

        # Right-aligned multi-line text view
        if not hasattr(macllm_ui, "top_bar_text_view"):
            top_bar_text_view = NSTextView.alloc().initWithFrame_(((text_field_x, text_y), (macllm_ui.top_bar_text_field_width, text_height)))
            top_bar_text_view.setString_("")
            top_bar_text_view.setDrawsBackground_(False)
            top_bar_text_view.setEditable_(False)
            top_bar_text_view.setSelectable_(False)
            top_bar_text_view.setTextContainerInset_((0.0, 0.0))

            paragraph_style = NSMutableParagraphStyle.alloc().init()
            paragraph_style.setAlignment_(2)  # right
            text_attributes = {
                NSFontAttributeName: NSFont.systemFontOfSize_(11.0),
                NSForegroundColorAttributeName: macllm_ui.text_grey_subtle,
                NSParagraphStyleAttributeName: paragraph_style,
            }
            top_bar_text_view.setTypingAttributes_(text_attributes)
            top_bar_container.addSubview_(top_bar_text_view)
            macllm_ui.top_bar_text_view = top_bar_text_view
        else:
            top_bar_text_view = macllm_ui.top_bar_text_view
            top_bar_text_view.setFrame_(((text_field_x, text_y), (macllm_ui.top_bar_text_field_width, text_height)))
            top_bar_text_view.setTextContainerInset_((0.0, 0.0))

        # Render context items area (step 1: single fixed pill)
        TopBarHandler.render_context_items(
            macllm_ui=macllm_ui,
            parent_view=top_bar_container,
            origin_x=context_area_x,
            origin_y=text_y,
            height=text_height,
            available_width=(text_field_x - context_area_x),
        )
