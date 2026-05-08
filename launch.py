"""Entry point for py2app. Adds the project root to sys.path for alias mode."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from macllm.macllm import main

if __name__ == "__main__":
    main()
