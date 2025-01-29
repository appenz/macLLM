import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from macllm.shortcuts import ShortCut

class MockMacLLM:
    def __init__(self, debug=False):
        self.debug = debug

class TestShortcuts(unittest.TestCase):
    def setUp(self):
        # Reset shortcuts before each test
        ShortCut.shortcuts = []
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, "config")
        os.makedirs(self.config_dir)

    def tearDown(self):
        # Clean up temp files
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_multiple_config_files(self):
        # Create multiple config files
        file1_content = '"@test1", "Test shortcut 1"\n'
        file2_content = '"@test2", "Test shortcut 2"\n'
        
        with open(os.path.join(self.config_dir, "shortcuts1.txt"), "w") as f:
            f.write(file1_content)
        with open(os.path.join(self.config_dir, "shortcuts2.txt"), "w") as f:
            f.write(file2_content)

        # Mock the app directory to point to our temp directory
        original_dirname = os.path.dirname
        try:
            os.path.dirname = lambda x: self.temp_dir

            # Initialize shortcuts
            mock_macllm = MockMacLLM(debug=True)
            ShortCut.init_shortcuts(mock_macllm)

            # Test that both shortcuts were loaded
            text = "@test1 and @test2"
            expanded = ShortCut.expandAll(text)
            self.assertEqual(expanded, "Test shortcut 1 and Test shortcut 2")
        finally:
            os.path.dirname = original_dirname

    def test_invalid_file_format(self):
        # Create a file with invalid format
        invalid_content = "invalid format\n@test1, Test 1\n"
        with open(os.path.join(self.config_dir, "invalid.txt"), "w") as f:
            f.write(invalid_content)

        # Mock the app directory
        original_dirname = os.path.dirname
        try:
            os.path.dirname = lambda x: self.temp_dir

            # Initialize shortcuts - should not raise any exceptions
            mock_macllm = MockMacLLM(debug=True)
            ShortCut.init_shortcuts(mock_macllm)

            # Test that invalid lines were skipped
            text = "@test1"
            expanded = ShortCut.expandAll(text)
            self.assertEqual(expanded, "@test1")  # Should remain unchanged
        finally:
            os.path.dirname = original_dirname

if __name__ == '__main__':
    unittest.main()