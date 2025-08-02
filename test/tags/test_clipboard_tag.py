import pytest
from unittest.mock import Mock, patch
from macllm.ui.core import MacLLMUI
from macllm.ui.input_field import InputFieldHandler


def test_input_text_preservation():
    """Test that input text is preserved between window sessions."""
    ui = MacLLMUI()
    
    # Simulate having some saved text
    ui.saved_input_text = "test input text"
    
    # Mock the necessary components
    mock_box = Mock()
    mock_input_container = Mock()
    mock_input_field = Mock()
    mock_delegate = Mock()
    
    with patch.object(InputFieldHandler, 'create_input_field') as mock_create:
        mock_create.return_value = (mock_input_container, mock_input_field, mock_delegate)
        
        # Call the method that would create the input field
        result = InputFieldHandler.create_input_field(mock_box, (0, 0), ui, ui.saved_input_text)
        
        # Verify the method was called with the saved text
        mock_create.assert_called_once_with(mock_box, (0, 0), ui, "test input text")
        
        # Verify the saved text is cleared after restoration
        assert ui.saved_input_text == ""


def test_close_window_saves_text():
    """Test that close_window saves the current input text."""
    ui = MacLLMUI()
    
    # Mock input field with some text
    mock_input_field = Mock()
    mock_input_field.string.return_value = "saved text"
    ui.input_field = mock_input_field
    
    # Mock window
    mock_window = Mock()
    ui.quick_window = mock_window
    
    # Mock app
    mock_app = Mock()
    ui.app = mock_app
    
    # Call close_window
    ui.close_window()
    
    # Verify the text was saved
    assert ui.saved_input_text == "saved text"
    mock_input_field.string.assert_called_once()


def test_clipboard_tag_plugin_loaded(app_fake):
    # plugin loaded?
    assert any(p.__class__.__name__ == "ClipboardTag" for p in app_fake.plugins)

def test_clipboard_tag_context_block(app_fake):
    # fake clipboard
    app_fake.ui.read_clipboard = lambda: "TEST_TOKEN"
    app_fake.handle_instructions("Summarize the text in @clipboard")

    # ensure prompt recorded by fake connector contains context block
    ctx = app_fake.llm.get_context_blocks()
    assert "clipboard" in ctx
    assert "TEST_TOKEN" in ctx["clipboard"]


# External end-to-end example (skipped unless OPENAI_API_KEY set)


@pytest.mark.external
def test_clipboard_tag_real(app_real):
    app_real.ui.read_clipboard = lambda: "What is 1+1? Answer only with a number."
    response = app_real.handle_instructions("Answer the question in @clipboard")
    assert response == "2"



