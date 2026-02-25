"""CLI entrypoint: python -m macllm.utils.screenshot"""

import sys
import argparse
from macllm.utils.screenshot import find_window, capture_window


def main():
    parser = argparse.ArgumentParser(
        description="Capture a screenshot of a macOS window by title"
    )
    parser.add_argument(
        "--title",
        default="macLLM",
        help="Substring to match in the window title (default: macLLM)",
    )
    parser.add_argument(
        "--output",
        default="./debug_screenshot.png",
        help="Output PNG path (default: ./debug_screenshot.png)",
    )
    args = parser.parse_args()

    wid = find_window(args.title)
    if wid is None:
        print(f"No visible window with '{args.title}' in title", file=sys.stderr)
        sys.exit(1)

    if capture_window(wid, args.output):
        print(f"Screenshot saved to {args.output}")
    else:
        print("Failed to capture window image", file=sys.stderr)
        sys.exit(1)


main()
