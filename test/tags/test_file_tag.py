import os
from unittest.mock import patch

import pytest

from macllm.tags.file_tag import FileTag


class DummyApp:
    """Minimal stub that satisfies FileTag's expectations."""

    debug = False

    def debug_log(self, *args, **kwargs):
        pass

    def debug_exception(self, *args, **kwargs):
        pass


@pytest.fixture

def filetag():
    return FileTag(DummyApp())


@pytest.mark.parametrize(
    "fragment,expected_dir,expected_prefix",
    [
        ("@~/", "~/", ""),
        ("@~/dev/proj", "~/dev/", "proj"),
        ("@/usr/loc", "/usr/", "loc"),
    ],
)
def test_parse_path_fragment(filetag, fragment, expected_dir, expected_prefix):
    dir_raw, prefix = filetag._parse_path_fragment(fragment)
    assert dir_raw == expected_dir
    assert prefix == expected_prefix


def test_autocomplete_live_files_and_dirs(tmp_path):
    base = tmp_path / "dev"
    base.mkdir()

    # File and directory to match the prefix "pro"
    (base / "project1.txt").write_text("x")
    (base / "project2").mkdir()
    (base / "other_file.txt").write_text("y")

    fragment = f'@"{base}/pro'
    tag = FileTag(DummyApp())
    suggestions = tag.autocomplete(fragment, max_results=10)

    # Expect both file and directory suggestions
    assert any("project1.txt" in s for s in suggestions)
    assert any("project2/" in s for s in suggestions)


def test_max_results_enforced(tmp_path):
    for i in range(20):
        (tmp_path / f"file{i}.txt").write_text("")
    fragment = f'@"{tmp_path}/f'
    tag = FileTag(DummyApp())
    results = tag.autocomplete(fragment, max_results=5)
    assert len(results) <= 5


def test_permission_error_handled(tmp_path):
    base = tmp_path / "dir"
    base.mkdir()
    tag = FileTag(DummyApp())
    with patch("os.scandir", side_effect=PermissionError):
        res = tag.autocomplete(f'@"{base}/x')
    assert res == []


def test_min_chars_not_enforced_for_paths(tmp_path):
    # '@/': only one char after '@' but should still return suggestions
    (tmp_path / "foo.txt").write_text("")
    frag = f'@"{tmp_path}/'
    tag = FileTag(DummyApp())
    sug = tag.autocomplete(frag, max_results=10)
    assert sug, "Expected suggestions even with < MIN_CHARS when path-like fragment"


def test_display_string_for_directory(tmp_path):
    base = tmp_path / "mydir"
    base.mkdir()
    tag = FileTag(DummyApp())
    suggestion = f'@"{base}/"'
    display = tag.display_string(suggestion)
    assert display.startswith("📁")
    assert "mydir" in display
