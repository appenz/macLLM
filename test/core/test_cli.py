import pytest
import subprocess
import sys
import os


class TestCommandLineOptions:
    """Test cases for command line argument parsing."""
    
    def test_version_flag(self):
        """Test that --version flag returns the version and exits."""
        # Get the path to the package root
        package_root = os.path.join(os.path.dirname(__file__), '..', '..')
        
        # Run the package module with --version flag
        result = subprocess.run([sys.executable, '-m', 'macllm', '--version'], 
                              capture_output=True, text=True, cwd=package_root)
        
        # Check that the command executed successfully (exit code 0)
        assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}"
        
        # Check that some output was produced (any output is a pass as requested)
        assert result.stdout.strip(), "Expected some output from --version flag"
        
        # Verify that the output contains a version string (any combination of numbers and periods)
        import re
        version_pattern = r'\d+(?:\.\d+)*'
        assert re.search(version_pattern, result.stdout), "Expected version string (numbers and periods) in output" 