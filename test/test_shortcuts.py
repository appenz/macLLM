import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from macllm.shortcuts import ShortCut

class TestShortcuts(unittest.TestCase):
    def setUp(self):
        # Reset shortcuts before each test
        ShortCut.shortcuts = []
        
        # Create a mock macllm object with debug flag
        self.mock_macllm = type('MockMacLLM', (), {'debug': True})()

    def test_default_shortcuts(self):
        """Test that default shortcuts from promptShortcuts are loaded"""
        ShortCut.init_shortcuts(self.mock_macllm)
        self.assertTrue(any(s.trigger == "@exp" for s in ShortCut.shortcuts))
        
    def test_multiple_config_locations(self):
        """Test reading shortcuts from multiple locations"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a temporary config structure
            config_dir = os.path.join(temp_dir, "config")
            os.makedirs(config_dir)
            
            # Create test config files
            with open(os.path.join(config_dir, "default_shortcuts.txt"), "w") as f:
                f.write('"@test1", "Test shortcut 1"\n')
            
            user_config_dir = os.path.join(temp_dir, ".config", "macllm")
            os.makedirs(user_config_dir)
            with open(os.path.join(user_config_dir, "shortcuts.txt"), "w") as f:
                f.write('"@test2", "Test shortcut 2"\n')
            
            with open(os.path.join(temp_dir, "myshortcuts.txt"), "w") as f:
                f.write('"@test3", "Test shortcut 3"\n')
            
            # Temporarily change working directory and home directory
            original_cwd = os.getcwd()
            original_home = os.environ.get('HOME')
            
            try:
                os.chdir(temp_dir)
                os.environ['HOME'] = temp_dir
                
                # Mock the app directory to be our temp directory
                import macllm.shortcuts
                original_abspath = os.path.abspath
                def mock_abspath(path):
                    if path == macllm.shortcuts.__file__:
                        return os.path.join(temp_dir, "macllm", "shortcuts.py")
                    return original_abspath(path)
                
                os.path.abspath = mock_abspath
                
                # Reset shortcuts and initialize
                ShortCut.shortcuts = []
                ShortCut.init_shortcuts(self.mock_macllm)
                
                # Restore original abspath
                os.path.abspath = original_abspath
                
                # Verify all shortcuts were loaded
                shortcuts = {s.trigger: s.prompt for s in ShortCut.shortcuts}
                self.assertIn("@test1", shortcuts)
                self.assertIn("@test2", shortcuts)
                self.assertIn("@test3", shortcuts)
                
            finally:
                os.chdir(original_cwd)
                if original_home:
                    os.environ['HOME'] = original_home
                else:
                    del os.environ['HOME']

    def test_invalid_format_handling(self):
        """Test handling of invalid format in config files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            shortcuts_path = os.path.join(temp_dir, "myshortcuts.txt")
            with open(shortcuts_path, "w") as f:
                f.write('"@valid", "This is valid"\n')
                f.write('"@invalid_no_second_part"\n')  # Invalid format
                f.write('"@valid2", "This is also valid"\n')

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                ShortCut.shortcuts = []  # Reset shortcuts
                ShortCut.init_shortcuts(self.mock_macllm)
                
                # Check that valid shortcuts were loaded
                shortcuts = {s.trigger: s.prompt for s in ShortCut.shortcuts}
                self.assertIn("@valid", shortcuts)
                self.assertIn("@valid2", shortcuts)
                
            finally:
                os.chdir(original_cwd)

    def test_shortcut_expansion(self):
        """Test that shortcuts are correctly expanded"""
        ShortCut("@test", "expanded test")
        text = "This is a @test message"
        expanded = ShortCut.expandAll(text)
        self.assertEqual(expanded, "This is a expanded test message")

if __name__ == '__main__':
    unittest.main()
