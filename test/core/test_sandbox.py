"""Tests for macllm.core.sandbox."""

import os
import platform
import tempfile

import pytest

from macllm.core.sandbox import build_profile, run_sandboxed


class TestBuildProfile:
    def test_profile_has_version(self):
        profile = build_profile(["/tmp/test"])
        assert "(version 1)" in profile

    def test_profile_denies_by_default(self):
        profile = build_profile(["/tmp/test"])
        assert "(deny default)" in profile

    def test_profile_imports_bsd(self):
        profile = build_profile(["/tmp/test"])
        assert '(import "bsd.sb")' in profile

    def test_profile_includes_granted_dir(self):
        profile = build_profile(["/tmp/testdir"])
        assert '(subpath "/private/tmp/testdir")' in profile
        assert "file-write*" in profile
        assert "process-exec" in profile

    def test_profile_allows_no_sandbox_exec_for_system_paths(self):
        profile = build_profile(["/tmp/test"])
        assert "(allow process-exec (with no-sandbox)" in profile

    def test_profile_includes_denied_paths(self):
        home = os.path.expanduser("~")
        profile = build_profile(["/tmp/test"])
        assert f'(subpath "{home}/.ssh")' in profile

    def test_profile_includes_system_paths(self):
        profile = build_profile(["/tmp/test"])
        assert '(subpath "/usr/bin")' in profile
        assert '(subpath "/bin")' in profile

    def test_profile_expands_tilde(self):
        profile = build_profile(["~/testdir"])
        home = os.path.expanduser("~")
        assert f'(subpath "{home}/testdir")' in profile

    def test_custom_read_only(self):
        profile = build_profile(["/tmp/test"], read_only_paths=["/custom/ro"])
        assert '(subpath "/custom/ro")' in profile

    def test_custom_denied(self):
        profile = build_profile(["/tmp/test"], denied_paths=["/custom/deny"])
        assert '(subpath "/custom/deny")' in profile

    def test_profile_allows_process_info(self):
        profile = build_profile(["/tmp/test"])
        assert "(allow process-info*)" in profile
        assert "(allow sysctl-read)" in profile


@pytest.fixture
def skip_non_macos():
    if platform.system() != "Darwin":
        pytest.skip("sandbox-exec only available on macOS")


class TestSandboxIntegration:
    """Integration tests that run commands under sandbox-exec."""

    def test_can_write_to_granted_dir(self, skip_non_macos):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_sandboxed(
                f"touch {tmpdir}/testfile",
                granted_dirs=[tmpdir],
            )
            assert result.returncode == 0
            assert os.path.exists(f"{tmpdir}/testfile")

    def test_cannot_write_outside_granted_dir(self, skip_non_macos):
        with tempfile.TemporaryDirectory() as allowed:
            target = os.path.expanduser("~/.macllm_sandbox_test_should_not_exist")
            if os.path.exists(target):
                os.remove(target)
            try:
                result = run_sandboxed(
                    f"touch {target}",
                    granted_dirs=[allowed],
                )
                assert result.returncode != 0
                assert not os.path.exists(target)
            finally:
                if os.path.exists(target):
                    os.remove(target)

    def test_cannot_read_home_directory(self, skip_non_macos):
        home = os.path.expanduser("~")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_sandboxed(
                f"ls {home}",
                granted_dirs=[tmpdir],
            )
            assert result.returncode != 0

    def test_can_read_system_binaries(self, skip_non_macos):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_sandboxed(
                "ls /usr/bin/env",
                granted_dirs=[tmpdir],
            )
            assert result.returncode == 0

    def test_cannot_read_ssh_dir(self, skip_non_macos):
        ssh_dir = os.path.expanduser("~/.ssh")
        if not os.path.isdir(ssh_dir):
            pytest.skip("~/.ssh does not exist")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_sandboxed(
                f"ls {ssh_dir}",
                granted_dirs=[tmpdir],
            )
            assert result.returncode != 0

    def test_can_read_granted_dir(self, skip_non_macos):
        with tempfile.TemporaryDirectory() as tmpdir:
            open(f"{tmpdir}/hello.txt", "w").close()
            result = run_sandboxed(
                f"ls {tmpdir}",
                granted_dirs=[tmpdir],
            )
            assert result.returncode == 0
            assert "hello.txt" in result.stdout

    def test_setuid_binary_ps(self, skip_non_macos):
        """Setuid binaries like /bin/ps run via (with no-sandbox) exemption."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_sandboxed("ps", granted_dirs=[tmpdir])
            assert result.returncode == 0
            assert "PID" in result.stdout

    def test_pipeline(self, skip_non_macos):
        """Pipelines work (shell can fork child processes)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_sandboxed("echo hello | grep hello", granted_dirs=[tmpdir])
            assert result.returncode == 0
            assert "hello" in result.stdout

    def test_can_execute_script_in_granted_dir(self, skip_non_macos):
        """Scripts in granted directories can be executed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script = os.path.join(tmpdir, "hello.sh")
            with open(script, "w") as f:
                f.write("#!/bin/sh\necho hello from script\n")
            os.chmod(script, 0o755)
            result = run_sandboxed(script, granted_dirs=[tmpdir])
            assert result.returncode == 0
            assert "hello from script" in result.stdout

    def test_cannot_execute_script_outside_granted_dir(self, skip_non_macos):
        """Scripts outside granted dirs cannot be executed."""
        with tempfile.TemporaryDirectory() as granted:
            with tempfile.TemporaryDirectory() as other:
                script = os.path.join(other, "sneaky.sh")
                with open(script, "w") as f:
                    f.write("#!/bin/sh\necho should not run\n")
                os.chmod(script, 0o755)
                result = run_sandboxed(script, granted_dirs=[granted])
                assert result.returncode != 0
