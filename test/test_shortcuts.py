import os
import tempfile
import unittest
from macllm.shortcuts import ShortCut

class TestShortcuts(unittest.TestCase):
    def setUp(self):
        # Reset shortcuts before each test
        ShortCut.shortcuts = []
        self.temp_dir = tempfile.mkdtemp()
        # Create config subdirectory
        self.config_dir = os.path.join(self.temp_dir, "config")
        os.makedirs(self.config_dir)
        
        # Create mock macllm class
        class MockMacLLM:
            debug = True
            def __init__(self, app_dir):
                self.app_dir = app_dir
                # Override config directories to only use our test directory
                self.config_dirs = [os.path.join(app_dir, "config")]
        self.MockMacLLM = MockMacLLM
        
    def tearDown(self):
        # Clean up test files
        import shutil
        shutil.rmtree(self.temp_dir)
        
    def create_test_config(self, content):
        config_path = os.path.join(self.config_dir, "test_shortcuts.toml")
        with open(config_path, "w") as f:
            f.write(content)
        return config_path
        
    def test_valid_toml_config(self):
        config = '''
shortcuts = [
    ["@test1", "Test Prompt 1"],
    ["@test2", "Test Prompt 2"]
]
'''
        config_path = self.create_test_config(config)
        
        mock_macllm = self.MockMacLLM(self.temp_dir)
        ShortCut.init_shortcuts(mock_macllm)
        
        # Verify shortcuts were loaded
        expanded = ShortCut.expandAll("@test1")
        self.assertEqual(expanded, "Test Prompt 1")
        
        expanded = ShortCut.expandAll("@test2")
        self.assertEqual(expanded, "Test Prompt 2")
        
    def test_invalid_toml_syntax(self):
        config = '''
shortcuts = [
    ["@test1", "Test Prompt 1"],
    ["@test2", Test Prompt 2]  # Missing quotes
]
'''
        config_path = self.create_test_config(config)
        
        mock_macllm = self.MockMacLLM(self.temp_dir)
        ShortCut.init_shortcuts(mock_macllm)
        
        # Verify no shortcuts were loaded from invalid file
        expanded = ShortCut.expandAll("@test1")
        self.assertEqual(expanded, "@test1")
        
    def test_missing_shortcuts_table(self):
        config = '''
other_table = []
'''
        config_path = self.create_test_config(config)
        
        mock_macllm = self.MockMacLLM(self.temp_dir)
        ShortCut.init_shortcuts(mock_macllm)
        
        # Verify no shortcuts were loaded
        expanded = ShortCut.expandAll("@test1")
        self.assertEqual(expanded, "@test1")
        
    def test_invalid_shortcut_format(self):
        config = '''
shortcuts = [
    ["@test1", "Test Prompt 1", "extra"],  # Too many elements
    ["@test2"]  # Too few elements
]
'''
        config_path = self.create_test_config(config)
        
        mock_macllm = self.MockMacLLM(self.temp_dir)
        ShortCut.init_shortcuts(mock_macllm)
        
        # Verify invalid shortcuts were not loaded
        expanded = ShortCut.expandAll("@test1")
        self.assertEqual(expanded, "@test1")
        expanded = ShortCut.expandAll("@test2")
        self.assertEqual(expanded, "@test2")
        
    def test_non_string_values(self):
        config = '''
shortcuts = [
    ["@test1", 123],  # Non-string value
    [123, "Test Prompt 2"]  # Non-string trigger
]
'''
        config_path = self.create_test_config(config)
        
        mock_macllm = self.MockMacLLM(self.temp_dir)
        ShortCut.init_shortcuts(mock_macllm)
        
        # Verify invalid shortcuts were not loaded
        expanded = ShortCut.expandAll("@test1")
        self.assertEqual(expanded, "@test1")
        
    def test_non_at_trigger(self):
        config = '''
shortcuts = [
    ["test1", "Test Prompt 1"],  # Missing @ in trigger
]
'''
        config_path = self.create_test_config(config)
        
        mock_macllm = self.MockMacLLM(self.temp_dir)
        ShortCut.init_shortcuts(mock_macllm)
        
        # Verify invalid shortcuts were not loaded
        expanded = ShortCut.expandAll("test1")
        self.assertEqual(expanded, "test1")

if __name__ == '__main__':
    unittest.main()
