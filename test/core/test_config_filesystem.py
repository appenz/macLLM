import pytest

from macllm.core.config import _from_dict


def test_filesystem_mount_config():
    config = _from_dict({
        "filesystem": {
            "mounts": {
                "notes": {
                    "virtual": "/notes/work",
                    "path": "~/Notes/work",
                    "supervisor_access": "read-write",
                    "subagent_access": "read-only",
                    "index": True,
                }
            }
        }
    })

    mount = config.filesystem.mounts["notes"]
    assert mount.virtual == "/notes/work"
    assert mount.supervisor_access == "read-write"
    assert mount.subagent_access == "read-only"
    assert mount.index is True


def test_filesystem_mount_requires_every_field():
    with pytest.raises(KeyError, match="index"):
        _from_dict({
            "filesystem": {
                "mounts": {
                    "incomplete": {
                        "virtual": "/data",
                        "path": "~/data",
                        "supervisor_access": "read-only",
                        "subagent_access": "none",
                    }
                }
            }
        })


def test_filesystem_mount_rejects_unknown_access():
    with pytest.raises(ValueError, match="Invalid filesystem access"):
        _from_dict({
            "filesystem": {
                "mounts": {
                    "bad": {
                        "virtual": "/data",
                        "path": "~/data",
                        "supervisor_access": "yes",
                        "subagent_access": "none",
                        "index": False,
                    }
                }
            }
        })
