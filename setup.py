"""
py2app build configuration for macLLM.

Usage:
    make app          # build dist/macLLM.app
    make app-clean    # remove build artifacts
"""

import sys
import tomllib
from setuptools import setup
import py2app.build_app  # noqa: F401 — force import so we can patch

sys.setrecursionlimit(10000)

# py2app 0.28.9+ rejects install_requires, but setuptools reads
# [project].dependencies from pyproject.toml and injects them.
# Clear install_requires right before py2app's check.
_orig_finalize = py2app.build_app.py2app.finalize_options
def _allow_pyproject_deps(self):
    self.distribution.install_requires = []
    _orig_finalize(self)
py2app.build_app.py2app.finalize_options = _allow_pyproject_deps

# py2app assumes zlib has a __file__, but on Python 3.13 it can be built-in.
# Patch copy_file to silently skip when the source is None.
_orig_copy_file = py2app.build_app.py2app.copy_file
def _copy_file_skip_builtin(self, infile, outfile, *args, **kwargs):
    if infile is None:
        return (outfile, 0)
    return _orig_copy_file(self, infile, outfile, *args, **kwargs)
py2app.build_app.py2app.copy_file = _copy_file_skip_builtin

import zlib as _zlib
if not hasattr(_zlib, "__file__"):
    _zlib.__file__ = None

with open("pyproject.toml", "rb") as f:
    _pyproject = tomllib.load(f)
    _version = _pyproject["project"]["version"]

APP = ["launch.py"]

DATA_FILES = [
    ("assets", ["assets/icon.png", "assets/icon-nobg.png", "assets/icon32x32.png"]),
]

OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "macLLM",
        "CFBundleDisplayName": "macLLM",
        "CFBundleIdentifier": "com.appenzeller.macllm",
        "CFBundleVersion": _version,
        "CFBundleShortVersionString": _version,
        "LSMinimumSystemVersion": "14.0",
        "NSMainNibFile": "",
        "NSMicrophoneUsageDescription": "macLLM needs microphone access for voice input.",
        "NSLocationWhenInUseUsageDescription": "macLLM uses your location to give the LLM local context.",
        "NSCalendarsUsageDescription": "macLLM reads your calendar to answer scheduling questions.",
    },
    "packages": ["macllm", "tiktoken"],
    "includes": [
        "objc",
        "AppKit",
        "Foundation",
        "Cocoa",
        "Quartz",
        "CoreLocation",
        "EventKit",
        "litellm",
        "smolagents",
        "openai",
        "certifi",
        "quickmachotkey",
        "markdown_it",
        "bs4",
        "bashlex",
        "tomli_w",
        "txtai",
        "tiktoken_ext.openai_public",
    ],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
    install_requires=[],
)
