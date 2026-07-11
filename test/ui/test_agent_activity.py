from macllm.core.conversation_log import (
    ConversationLog,
    add_tool_call,
    append_activity_marker,
    append_run_start,
    append_step,
)
from macllm.ui.agent_activity import extract_update, project_activity, without_update


def _planning(log, update, agent="default"):
    append_step(log, {
        "agent_name": agent,
        "agent_role": "parent" if agent == "default" else "subagent",
        "step_type": "planning",
        "model_output": f"### Plan:\n[ ] Goal\n<update>{update}</update>\n<end_plan>",
    })


def test_extract_update_is_independent_of_plan_item():
    text = (
        "### Plan:\n[ ] Find the OpenAI founders\n"
        "<update>\nSearching for Sam's last name\n</update>\n<end_plan>"
    )
    assert extract_update(text) == "Searching for Sam's last name"
    assert extract_update("### Plan:\n[ ] Goal\n<end_plan>") is None
    assert without_update("[ ] Goal\n<update>Searching</update>") == "[ ] Goal"


def test_parent_planning_update_is_ephemeral_then_persistent():
    log = ConversationLog()
    append_run_start(log, {})
    append_activity_marker(log, "planning_started", "default")
    assert project_activity(log, "default") == ([], ("planning", None))

    _planning(log, "Searching for Sam's last name")
    assert project_activity(log, "default") == (
        [],
        ("update", "Searching for Sam's last name"),
    )

    append_activity_marker(log, "action_started", "default")
    assert project_activity(log, "default") == (
        ["Searching for Sam's last name"],
        None,
    )

    add_tool_call(log, "web_search", "Searching the web")
    assert project_activity(log, "default") == (
        ["Searching for Sam's last name"],
        ("tool", {"tool": "web_search", "message": "Searching the web"}),
    )


def test_subagent_activity_never_promotes_an_update():
    log = ConversationLog()
    append_run_start(log, {})
    append_activity_marker(log, "planning_started", "default")
    _planning(log, "Reading the latest email")
    append_activity_marker(log, "action_started", "default")
    append_step(log, {
        "agent_name": "email",
        "agent_role": "subagent",
        "step_type": "task",
        "task": "Read the latest email",
        "observations": None,
    })
    append_activity_marker(log, "action_started", "email")

    assert project_activity(log, "default") == (
        ["Reading the latest email"],
        ("subagent", "email"),
    )

    add_tool_call(log, "search_email", "Searching email")
    assert project_activity(log, "default") == (
        ["Reading the latest email"],
        ("tool", {"tool": "search_email", "message": "Searching email"}),
    )

    append_step(log, {
        "agent_name": "default",
        "agent_role": "parent",
        "step_type": "action",
        "observations": "email report",
    })
    assert project_activity(log, "default") == (["Reading the latest email"], None)
