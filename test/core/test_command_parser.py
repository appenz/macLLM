"""Tests for macllm.core.command_parser."""

import os

import pytest

from macllm.core.command_parser import CommandParseError, extract_executables, extract_paths


class TestExtractExecutables:
    def test_simple_command(self):
        assert extract_executables("ls -la") == ["ls"]

    def test_command_with_args(self):
        assert extract_executables("git log --oneline") == ["git"]

    def test_pipeline(self):
        assert extract_executables("grep foo file.txt | wc -l") == ["grep", "wc"]

    def test_long_pipeline(self):
        result = extract_executables("git log --oneline | head -20 | grep fix")
        assert result == ["git", "head", "grep"]

    def test_chain_and(self):
        assert extract_executables("cd /tmp && ls") == ["cd", "ls"]

    def test_chain_or(self):
        assert extract_executables("test -f foo || echo missing") == ["test", "echo"]

    def test_chain_semicolon(self):
        assert extract_executables("echo hello; echo world") == ["echo"]

    def test_command_substitution(self):
        result = extract_executables("echo $(curl example.com)")
        assert "echo" in result
        assert "curl" in result

    def test_absolute_path(self):
        assert extract_executables("/usr/bin/env python") == ["env"]

    def test_env_var_assignment(self):
        result = extract_executables("FOO=bar baz")
        assert result == ["baz"]

    def test_deduplication(self):
        result = extract_executables("echo a; echo b")
        assert result == ["echo"]

    def test_empty_command(self):
        with pytest.raises(CommandParseError):
            extract_executables("")

    def test_whitespace_only(self):
        with pytest.raises(CommandParseError):
            extract_executables("   ")

    def test_unparseable(self):
        with pytest.raises(CommandParseError):
            extract_executables("$((")


class TestExtractPaths:
    def test_tilde_path(self):
        result = extract_paths("ls ~")
        assert result == [os.path.expanduser("~")]

    def test_tilde_subdir(self):
        result = extract_paths("ls ~/Documents")
        assert result == [os.path.expanduser("~/Documents")]

    def test_absolute_path(self):
        result = extract_paths("cat /etc/hosts")
        assert result == ["/etc/hosts"]

    def test_relative_dot(self):
        result = extract_paths("ls ./src")
        assert os.path.isabs(result[0])

    def test_no_paths(self):
        assert extract_paths("echo hello world") == []

    def test_flags_are_not_paths(self):
        assert extract_paths("ls -la") == []

    def test_skips_executable(self):
        result = extract_paths("/usr/bin/ls ~/foo")
        assert len(result) == 1
        assert result[0] == os.path.expanduser("~/foo")

    def test_pipeline_paths(self):
        result = extract_paths("grep pattern ~/file.txt | wc -l")
        assert result == [os.path.expanduser("~/file.txt")]

    def test_chain_paths(self):
        result = extract_paths("ls ~/a && cat ~/b")
        home = os.path.expanduser("~")
        assert os.path.join(home, "a") in result
        assert os.path.join(home, "b") in result

    def test_deduplication(self):
        result = extract_paths("cat ~/file.txt && head ~/file.txt")
        assert len(result) == 1

    def test_empty_command(self):
        assert extract_paths("") == []

    def test_unparseable_returns_empty(self):
        assert extract_paths("$((") == []
