"""Shared fixtures for note tool tests."""

import pytest
from unittest.mock import MagicMock

from macllm.core import config as config_mod
from macllm.core.config import FilesystemConfig, FilesystemMountConfig, MacLLMConfig
from macllm.tags.file_tag import FileTag

MOUNT_VIRTUAL = "/notes/Notes"


class DummyApp:
    """Minimal stand-in for MacLLM used by note tool tests."""

    class _Args:
        debug = False

    args = _Args()

    def debug_log(self, *a, **kw):
        pass

    def debug_exception(self, *a, **kw):
        pass


@pytest.fixture
def file_env(tmp_path):
    """Set up FileTag with an indexed directory containing sample files.

    Yields the tmp_path.  Cleans up FileTag and MacLLM._instance afterwards.
    """
    from macllm.macllm import MacLLM

    (tmp_path / "alpha.md").write_text("Alpha content about travel")
    (tmp_path / "beta.txt").write_text("Beta content about recipes")

    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "gamma.md").write_text("Gamma nested content")

    dummy = DummyApp()
    previous_config = config_mod._RUNTIME_CONFIG
    config_mod._RUNTIME_CONFIG = MacLLMConfig(
        filesystem=FilesystemConfig({
            "Notes": FilesystemMountConfig(
                MOUNT_VIRTUAL,
                str(tmp_path),
                "read-write",
                "read-only",
                True,
            )
        })
    )
    FileTag._macllm = dummy
    MacLLM._instance = dummy
    FileTag._indexed_directories = [str(tmp_path)]
    FileTag._index = [
        ("alpha.md", str(tmp_path / "alpha.md")),
        ("beta.txt", str(tmp_path / "beta.txt")),
        ("gamma.md", str(sub / "gamma.md")),
    ]
    FileTag._filepath_to_idx = {
        str(tmp_path / "alpha.md"): 0,
        str(tmp_path / "beta.txt"): 1,
        str(sub / "gamma.md"): 2,
    }

    yield tmp_path

    config_mod._RUNTIME_CONFIG = previous_config
    FileTag._index = []
    FileTag._indexed_directories = []
    FileTag._filepath_to_idx = {}
    FileTag._macllm = None
    MacLLM._instance = None
