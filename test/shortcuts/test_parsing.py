import pytest
import subprocess
import sys
import os


class TestShortcutParsing:
    """Test cases for parsing shortcuts with whitespaces"""
    
    # Test cases: (input_string, expected_shortcut_or_none)
    # If expected_shortcut_or_none is None, no shortcuts should be found
    # If expected_shortcut_or_none is a string, exactly one shortcut should be found with that content
    test_cases = [
        # Strings without shortcuts (should find no shortcuts)
        ("This is a test", None),
        (r"This \ is a backslash", None),
        ("This \" is a quote", None),
        ("""
This is indented text:
AAA
    BBB
        CCC
        """, None),
        ("Quote Test \"inside\" outside", None),
        ("", None),
        
        # Rule 1: Shortcut ends at first whitespace
        ("@~/My Home/foo", "@~/My"),
        ("@/path/to/file.txt content", "@/path/to/file.txt"),
        ("@clipboard some text", "@clipboard"),
        ("@window analyze this", "@window"),
        
        # Rule 2: Backslash-escaped spaces are included
        (r"@~/My\ Home/foo", r"@~/My Home/foo"),
        (r"@/path/with\ spaces/file.txt", r"@/path/with spaces/file.txt"),
        
        # Rule 3: Quoted shortcuts include everything until closing quote (quotes are stripped)
        ('@"~/My Home/foo"', '@~/My Home/foo'),
        ('@"https://example.com/path with spaces"', '@https://example.com/path with spaces'),
        
        # Mixed cases
        (r"@~/My\ Home/foo rest of text", r"@~/My Home/foo"),
        ('@"~/My Home/foo" rest of text', '@~/My Home/foo'),
        
        # Edge case: Quoted shortcuts ending at newlines
        ('@"~/My Home/foo\nrest of text', '@~/My Home/foo'),
    ]
    
    def test_shortcut_parsing(self):
        """Test that shortcuts are correctly parsed according to the rules"""
        from macllm.core.user_request import UserRequest
        
        for input_string, expected_shortcut in self.test_cases:
            # Find shortcuts in the input string
            print(f"Input string: {input_string}")
            shortcuts = UserRequest.find_shortcuts(input_string)
            print(f"Shortcuts: {shortcuts}")
            
            if expected_shortcut is None:
                # Should find no shortcuts
                assert len(shortcuts) == 0, \
                    f"Found unexpected shortcuts in string: '{input_string}' -> {shortcuts}"
            else:
                # Should find exactly one shortcut
                assert len(shortcuts) == 1, \
                    f"Expected 1 shortcut in '{input_string}', found {len(shortcuts)}: {shortcuts}"
                
                # Check that the shortcut content matches expected
                start_pos, end_pos, shortcut_text = shortcuts[0]
                assert shortcut_text == expected_shortcut, \
                    f"Shortcut mismatch for '{input_string}': expected '{expected_shortcut}', got '{shortcut_text}'"
                
                # Verify the shortcut is at the beginning of the string
                assert start_pos == 0, \
                    f"Shortcut should start at position 0 for '{input_string}', but starts at {start_pos}"