"""Tests for shell config loading."""

from macllm.core.config import _from_dict, _DEFAULT_ALLOWED_COMMANDS, _DEFAULT_DIRS, _DEFAULT_READ_ONLY_PATHS


class TestShellConfigDefaults:
    def test_defaults_when_no_shell_section(self):
        config = _from_dict({})
        assert config.shell.allowed_commands == list(_DEFAULT_ALLOWED_COMMANDS)
        assert config.shell.default_dirs == list(_DEFAULT_DIRS)
        assert config.shell.read_only_paths == list(_DEFAULT_READ_ONLY_PATHS)

    def test_custom_allowed_commands(self):
        data = {"shell": {"allowed_commands": ["ls", "git"]}}
        config = _from_dict(data)
        assert config.shell.allowed_commands == ["ls", "git"]

    def test_custom_default_dirs(self):
        data = {"shell": {"default_dirs": ["~/projects"]}}
        config = _from_dict(data)
        assert config.shell.default_dirs == ["~/projects"]

    def test_custom_read_only_paths(self):
        data = {"shell": {"read_only_paths": ["/custom/path"]}}
        config = _from_dict(data)
        assert config.shell.read_only_paths == ["/custom/path"]

    def test_empty_shell_section(self):
        data = {"shell": {}}
        config = _from_dict(data)
        assert config.shell.allowed_commands == list(_DEFAULT_ALLOWED_COMMANDS)
