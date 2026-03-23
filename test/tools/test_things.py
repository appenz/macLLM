"""Things tool tests against the real Things app and database.

Run with: make test-things

These tests only create uniquely prefixed items and only mutate those created
items. They require Things URL access to be enabled and an auth token to be
present in the database.
"""

import uuid

import pytest

from macllm.core.agent_status import AgentStatusManager

TEST_PREFIX = f"__macllm_things_test_{uuid.uuid4().hex[:8]}"


class DummyApp:
    class _Args:
        debug = False

    args = _Args()

    def __init__(self):
        self.status_manager = AgentStatusManager()

    def debug_log(self, *a, **kw):
        pass

    def debug_exception(self, *a, **kw):
        pass


@pytest.fixture(autouse=True)
def _patch_macllm():
    """Wire up a DummyApp so status reporting works inside tools."""
    from macllm.macllm import MacLLM

    MacLLM._instance = DummyApp()
    yield
    MacLLM._instance = None


@pytest.fixture()
def created_items():
    """Collect created item IDs and best-effort cancel them on teardown."""
    items: list[str] = []
    yield items

    if not items:
        return

    from macllm.tools.things import things_cancel_item

    for item_id in reversed(items):
        try:
            things_cancel_item(item_id=item_id, canceled=True)
        except Exception:
            pass


def _extract_id(result: str) -> str:
    for line in result.splitlines():
        if line.strip().startswith("ID:"):
            return line.split("ID:", 1)[1].strip()
    raise AssertionError(f"Could not extract Things ID from result:\n{result}")


@pytest.mark.things
def test_things_auth_token_present():
    import things

    token = things.token()
    assert token, "Things URL auth token is required for make test-things"


@pytest.mark.things
def test_list_reads_return_strings():
    from macllm.tools.things import (
        things_list_areas,
        things_list_projects,
        things_list_tags,
        things_list_todos,
    )

    assert isinstance(things_list_areas(), str)
    assert isinstance(things_list_projects(), str)
    assert isinstance(things_list_tags(), str)
    assert isinstance(things_list_todos(bucket="inbox"), str)


@pytest.mark.things
def test_create_and_get_todo(created_items):
    from macllm.tools.things import things_create_todo, things_get_item

    title = f"{TEST_PREFIX}_todo"
    result = things_create_todo(title=title, notes="integration test")
    assert "To-do created" in result
    assert title in result

    item_id = _extract_id(result)
    created_items.append(item_id)

    fetched = things_get_item(item_id=item_id)
    assert title in fetched
    assert item_id in fetched


@pytest.mark.things
def test_create_move_complete_and_cancel(created_items):
    from macllm.tools.things import (
        things_cancel_item,
        things_complete_item,
        things_create_project,
        things_create_todo,
        things_update_todo,
    )

    project_title = f"{TEST_PREFIX}_project"
    project_result = things_create_project(title=project_title)
    assert "Project created" in project_result
    assert project_title in project_result
    project_id = _extract_id(project_result)
    created_items.append(project_id)

    todo_title = f"{TEST_PREFIX}_move_me"
    todo_result = things_create_todo(title=todo_title)
    assert "To-do created" in todo_result
    todo_id = _extract_id(todo_result)
    created_items.append(todo_id)

    moved = things_update_todo(item_id=todo_id, list_id=project_id)
    assert "To-do updated" in moved
    assert project_title in moved

    completed = things_complete_item(item_id=todo_id)
    assert "Status: completed" in completed

    reopened = things_complete_item(item_id=todo_id, completed=False)
    assert "Status: incomplete" in reopened

    canceled = things_cancel_item(item_id=todo_id)
    assert "Status: canceled" in canceled
