"""Things tools using the local DB for reads and URL scheme for writes."""

from __future__ import annotations

import subprocess
import time
from datetime import datetime, timezone
from typing import Any

from smolagents import tool

_tool_call_counter = {
    "things_list_areas": 0,
    "things_list_projects": 0,
    "things_list_tags": 0,
    "things_list_todos": 0,
    "things_search": 0,
    "things_get_item": 0,
    "things_show_item": 0,
    "things_create_todo": 0,
    "things_create_project": 0,
    "things_update_todo": 0,
    "things_update_project": 0,
    "things_complete_item": 0,
    "things_cancel_item": 0,
}

def _things():
    import things

    return things


def _get_database():
    return _things().Database()


def _status_manager():
    from macllm.macllm import MacLLM

    return MacLLM.get_status_manager()


def _make_tool_id(name: str) -> str:
    _tool_call_counter[name] += 1
    return f"{name}_{_tool_call_counter[name]}_{int(time.time() * 1000)}"


def _strip(value: str) -> str:
    return value.strip() if isinstance(value, str) else value


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_created(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _require_write_access() -> str:
    token = _things().token(database=_get_database())
    if not token:
        raise ValueError(
            "Things URL auth token is unavailable. Enable Things URLs in Things settings first."
        )
    return token


def _open_things_url(command: str, uuid: str | None = None, **query_parameters) -> str:
    if command in {"add", "add-project", "update", "update-project"}:
        _require_write_access()

    uri = _things().url(uuid=uuid, command=command, **query_parameters)
    result = subprocess.run(
        ["open", uri],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "open failed").strip()
        raise RuntimeError(f"Failed to open Things URL: {stderr}")

    time.sleep(0.2)
    return uri


def _normalize_status(status: str) -> str | None:
    status = _strip(status)
    if not status or status.lower() in {"all", "any"}:
        return None
    valid = {"incomplete", "completed", "canceled"}
    if status not in valid:
        raise ValueError(
            f"Invalid status '{status}'. Use incomplete, completed, canceled, or leave blank."
        )
    return status


def _resolve_area_id(area: str) -> str | None:
    area = _strip(area)
    if not area:
        return None

    areas = _things().areas(database=_get_database())
    id_matches = [item for item in areas if item["uuid"] == area]
    if id_matches:
        return id_matches[0]["uuid"]

    matches = [item for item in areas if item["title"].casefold() == area.casefold()]
    if not matches:
        raise ValueError(f"No Things area found matching '{area}'.")
    if len(matches) > 1:
        ids = ", ".join(item["uuid"] for item in matches)
        raise ValueError(f"Multiple Things areas match '{area}': {ids}")
    return matches[0]["uuid"]


def _resolve_project_id(project: str) -> str | None:
    project = _strip(project)
    if not project:
        return None

    projects = _things().projects(status=None, database=_get_database())
    id_matches = [item for item in projects if item["uuid"] == project]
    if id_matches:
        return id_matches[0]["uuid"]

    matches = [item for item in projects if item["title"].casefold() == project.casefold()]
    if not matches:
        raise ValueError(f"No Things project found matching '{project}'.")
    if len(matches) > 1:
        ids = ", ".join(item["uuid"] for item in matches)
        raise ValueError(f"Multiple Things projects match '{project}': {ids}")
    return matches[0]["uuid"]


def _resolve_project_or_area_id(list_id: str, list_name: str) -> str | None:
    list_id = _strip(list_id)
    if list_id:
        item = _things().get(list_id, default=None, database=_get_database())
        if item is None or item.get("type") not in {"project", "area"}:
            raise ValueError(f"Things list-id '{list_id}' is not a project or area.")
        return list_id

    list_name = _strip(list_name)
    if not list_name:
        return None

    areas = _things().areas(database=_get_database())
    projects = _things().projects(status=None, database=_get_database())
    matches = [
        item
        for item in [*areas, *projects]
        if item["title"].casefold() == list_name.casefold()
    ]
    if not matches:
        raise ValueError(f"No Things project or area found matching '{list_name}'.")
    if len(matches) > 1:
        details = ", ".join(f"{item['type']}:{item['uuid']}" for item in matches)
        raise ValueError(f"Multiple Things lists match '{list_name}': {details}")
    return matches[0]["uuid"]


def _resolve_heading_id(project_id: str | None, heading_id: str, heading: str) -> str | None:
    heading_id = _strip(heading_id)
    heading = _strip(heading)
    if heading_id:
        return heading_id
    if not heading:
        return None
    if not project_id:
        raise ValueError("A project/list must be specified when referring to a heading by title.")

    project = _things().projects(project_id, include_items=True, database=_get_database())
    headings = [
        item
        for item in project.get("items", [])
        if item.get("type") == "heading" and item.get("title", "").casefold() == heading.casefold()
    ]
    if not headings:
        raise ValueError(f"No heading named '{heading}' found in that project.")
    if len(headings) > 1:
        ids = ", ".join(item["uuid"] for item in headings)
        raise ValueError(f"Multiple headings named '{heading}' found in that project: {ids}")
    return headings[0]["uuid"]


def _load_item(item_id: str, include_items: bool = True) -> dict[str, Any]:
    item = _things().get(item_id, default=None, include_items=include_items, database=_get_database())
    if item is None:
        raise ValueError(f"No Things item found for ID '{item_id}'.")
    return item


def _wait_for_item(item_id: str, timeout_seconds: float = 5.0) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_error = None
    while time.time() < deadline:
        try:
            return _load_item(item_id, include_items=True)
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)
    if last_error:
        raise last_error
    raise TimeoutError(f"Timed out waiting for Things item '{item_id}'.")


def _find_recent_created_item(
    *,
    title: str,
    item_type: str,
    created_after: datetime,
    list_id: str | None = None,
    area_id: str | None = None,
) -> dict[str, Any] | None:
    items = _things().last("1d", type=item_type, status=None, database=_get_database())
    for item in items:
        if item.get("title") != title:
            continue
        created = _parse_created(item.get("created"))
        if created is None or created < created_after:
            continue
        if list_id and item.get("project") != list_id and item.get("area") != list_id:
            continue
        if area_id and item.get("area") != area_id:
            continue
        return _load_item(item["uuid"], include_items=True)
    return None


def _wait_for_recent_created_item(
    *,
    title: str,
    item_type: str,
    created_after: datetime,
    list_id: str | None = None,
    area_id: str | None = None,
    timeout_seconds: float = 5.0,
) -> dict[str, Any] | None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        item = _find_recent_created_item(
            title=title,
            item_type=item_type,
            created_after=created_after,
            list_id=list_id,
            area_id=area_id,
        )
        if item is not None:
            return item
        time.sleep(0.2)
    return None


def _set_if_present(params: dict[str, Any], key: str, value: str) -> None:
    value = _strip(value)
    if value == "":
        return
    params[key] = value


def _set_if_present_or_clear(params: dict[str, Any], key: str, value: str) -> None:
    value = _strip(value)
    if value == "":
        return
    params[key] = "" if value == "CLEAR" else value


def _bucket_items(bucket: str, **kwargs):
    bucket = _strip(bucket).lower()
    things = _things()
    if not bucket:
        return things.todos(**kwargs)
    if bucket == "inbox":
        return things.inbox(**kwargs)
    if bucket == "today":
        kwargs.pop("status", None)
        return things.today(**kwargs)
    if bucket == "upcoming":
        kwargs.pop("status", None)
        return things.upcoming(**kwargs)
    if bucket == "anytime":
        kwargs.pop("status", None)
        return things.anytime(**kwargs)
    if bucket == "someday":
        kwargs.pop("status", None)
        return things.someday(**kwargs)
    if bucket == "logbook":
        kwargs.pop("status", None)
        return things.logbook(**kwargs)
    if bucket == "trash":
        return things.trash(**kwargs)
    if bucket == "deadlines":
        kwargs.pop("status", None)
        return things.deadlines(**kwargs)
    raise ValueError(
        "Invalid bucket. Use inbox, today, upcoming, anytime, someday, logbook, trash, deadlines, or leave blank."
    )


def _format_checklist(items: list[dict[str, Any]], indent: str = "  ") -> list[str]:
    status_map = {
        "completed": "x",
        "canceled": "-",
        "incomplete": " ",
    }
    lines = [f"{indent}Checklist:"]
    for item in items:
        marker = status_map.get(item.get("status", "incomplete"), " ")
        lines.append(f"{indent}  - [{marker}] {item.get('title', '(untitled)')}")
    return lines


def _format_nested_items(items: list[dict[str, Any]], indent: str = "  ") -> list[str]:
    lines = [f"{indent}Items:"]
    for item in items:
        lines.append(
            f"{indent}  - {item.get('title', '(untitled)')} ({item.get('type', 'item')}, ID: {item.get('uuid', '?')})"
        )
    return lines


def _format_item(item: dict[str, Any]) -> str:
    item_type = item.get("type", "item")
    title = item.get("title", "(untitled)")
    lines = [f"- {title} ({item_type})"]

    if item.get("uuid"):
        lines.append(f"  ID: {item['uuid']}")
    if item.get("status"):
        lines.append(f"  Status: {item['status']}")
    if item.get("trashed"):
        lines.append("  Trashed: yes")
    if item.get("start"):
        lines.append(f"  List: {item['start']}")
    if item.get("start_date"):
        lines.append(f"  Start date: {item['start_date']}")
    if item.get("deadline"):
        lines.append(f"  Deadline: {item['deadline']}")
    if item.get("reminder_time"):
        lines.append(f"  Reminder time: {item['reminder_time']}")
    if item.get("area_title"):
        lines.append(f"  Area: {item['area_title']}")
    if item.get("project_title"):
        lines.append(f"  Project: {item['project_title']}")
    if item.get("heading_title"):
        lines.append(f"  Heading: {item['heading_title']}")
    if item.get("tags"):
        if isinstance(item["tags"], list):
            lines.append(f"  Tags: {', '.join(item['tags'])}")
        else:
            lines.append("  Tags: yes")
    if item.get("shortcut"):
        lines.append(f"  Shortcut: {item['shortcut']}")
    if item.get("created"):
        lines.append(f"  Created: {item['created']}")
    if item.get("modified"):
        lines.append(f"  Modified: {item['modified']}")
    if item.get("stop_date"):
        lines.append(f"  Stop date: {item['stop_date']}")
    if item.get("notes"):
        lines.append(f"  Notes: {item['notes']}")
    if isinstance(item.get("checklist"), list) and item["checklist"]:
        lines.extend(_format_checklist(item["checklist"]))
    if isinstance(item.get("items"), list) and item["items"]:
        lines.extend(_format_nested_items(item["items"]))

    return "\n".join(lines)


def _format_items(items: list[dict[str, Any]], empty_message: str) -> str:
    if not items:
        return empty_message
    return "\n\n".join(_format_item(item) for item in items)


def _update_command_for_item(item: dict[str, Any]) -> str:
    item_type = item.get("type")
    if item_type == "to-do":
        return "update"
    if item_type == "project":
        return "update-project"
    raise ValueError(f"Things item type '{item_type}' does not support this operation.")


@tool
def things_list_areas() -> str:
    """
    List all Things areas from the local Things database.

    Returns:
        A formatted list of areas and their IDs.
    """
    tool_id = _make_tool_id("things_list_areas")
    status = _status_manager()
    status.start_tool_call(tool_id, "things_list_areas", {})
    try:
        items = _things().areas(database=_get_database())
        result = _format_items(items, "No Things areas found.")
        status.complete_tool_call(tool_id, f"{len(items)} areas")
        return result
    except Exception as exc:
        status.fail_tool_call(tool_id, str(exc)[:80])
        raise


@tool
def things_list_projects(area: str = "", include_completed: bool = False) -> str:
    """
    List Things projects, optionally scoped to an area.

    Args:
        area: Optional area title or ID to filter by.
        include_completed: Set to true to include completed and canceled projects.

    Returns:
        A formatted list of projects and their IDs.
    """
    tool_id = _make_tool_id("things_list_projects")
    status = _status_manager()
    status.start_tool_call(tool_id, "things_list_projects", {"area": area})
    try:
        area_id = _resolve_area_id(area)
        items = _things().projects(
            area=area_id,
            status=None if include_completed else "incomplete",
            database=_get_database(),
        )
        result = _format_items(items, "No Things projects found.")
        status.complete_tool_call(tool_id, f"{len(items)} projects")
        return result
    except Exception as exc:
        status.fail_tool_call(tool_id, str(exc)[:80])
        raise


@tool
def things_list_tags() -> str:
    """
    List all Things tags from the local Things database.

    Returns:
        A formatted list of tags.
    """
    tool_id = _make_tool_id("things_list_tags")
    status = _status_manager()
    status.start_tool_call(tool_id, "things_list_tags", {})
    try:
        items = _things().tags(database=_get_database())
        result = _format_items(items, "No Things tags found.")
        status.complete_tool_call(tool_id, f"{len(items)} tags")
        return result
    except Exception as exc:
        status.fail_tool_call(tool_id, str(exc)[:80])
        raise


@tool
def things_list_todos(
    bucket: str = "",
    area: str = "",
    project: str = "",
    tag: str = "",
    status: str = "incomplete",
    include_checklist: bool = False,
) -> str:
    """
    List Things to-dos from the local Things database.

    Args:
        bucket: Optional bucket such as inbox, today, upcoming, anytime, someday, logbook, trash, or deadlines.
        area: Optional area title or ID to filter by.
        project: Optional project title or ID to filter by.
        tag: Optional tag title to filter by.
        status: Optional status filter. Use incomplete, completed, canceled, all, or leave blank.
        include_checklist: Set to true to include checklist items in returned to-dos.

    Returns:
        A formatted list of to-dos.
    """
    tool_id = _make_tool_id("things_list_todos")
    status_mgr = _status_manager()
    status_mgr.start_tool_call(tool_id, "things_list_todos", {"bucket": bucket or "all"})
    try:
        area_id = _resolve_area_id(area)
        project_id = _resolve_project_id(project)
        items = _bucket_items(
            bucket,
            area=area_id,
            project=project_id,
            tag=_strip(tag) or None,
            status=_normalize_status(status),
            include_items=include_checklist,
            database=_get_database(),
        )
        result = _format_items(items, "No Things to-dos found.")
        status_mgr.complete_tool_call(tool_id, f"{len(items)} todos")
        return result
    except Exception as exc:
        status_mgr.fail_tool_call(tool_id, str(exc)[:80])
        raise


@tool
def things_search(query: str, status: str = "", limit: int = 25) -> str:
    """
    Search Things data by text.

    Args:
        query: Search text. Matches titles and notes in Things.
        status: Optional status filter. Use incomplete, completed, canceled, all, or leave blank.
        limit: Maximum number of matches to return.

    Returns:
        A formatted list of matching Things items.
    """
    tool_id = _make_tool_id("things_search")
    status_mgr = _status_manager()
    status_mgr.start_tool_call(tool_id, "things_search", {"query": query})
    try:
        matches = _things().search(
            _strip(query),
            status=_normalize_status(status),
            trashed=False,
            database=_get_database(),
        )
        matches = matches[:limit]
        result = _format_items(matches, f"No Things items found matching '{query}'.")
        status_mgr.complete_tool_call(tool_id, f"{len(matches)} matches")
        return result
    except Exception as exc:
        status_mgr.fail_tool_call(tool_id, str(exc)[:80])
        raise


@tool
def things_get_item(item_id: str, include_items: bool = True) -> str:
    """
    Get a single Things item by ID.

    Args:
        item_id: The Things item ID.
        include_items: Include nested items and checklist data when available.

    Returns:
        The formatted item details.
    """
    tool_id = _make_tool_id("things_get_item")
    status_mgr = _status_manager()
    status_mgr.start_tool_call(tool_id, "things_get_item", {"item_id": item_id})
    try:
        item = _load_item(_strip(item_id), include_items=include_items)
        result = _format_item(item)
        status_mgr.complete_tool_call(tool_id, item.get("title", item_id)[:30])
        return result
    except Exception as exc:
        status_mgr.fail_tool_call(tool_id, str(exc)[:80])
        raise


@tool
def things_show_item(item_id: str) -> str:
    """
    Reveal a Things item in the Things app.

    Args:
        item_id: The Things item ID.

    Returns:
        The formatted item details after revealing it in Things.
    """
    tool_id = _make_tool_id("things_show_item")
    status_mgr = _status_manager()
    status_mgr.start_tool_call(tool_id, "things_show_item", {"item_id": item_id})
    try:
        item = _load_item(_strip(item_id), include_items=True)
        _open_things_url("show", uuid=item["uuid"])
        result = "Opened in Things:\n\n" + _format_item(item)
        status_mgr.complete_tool_call(tool_id, item.get("title", item_id)[:30])
        return result
    except Exception as exc:
        status_mgr.fail_tool_call(tool_id, str(exc)[:80])
        raise


@tool
def things_create_todo(
    title: str,
    when: str = "",
    deadline: str = "",
    notes: str = "",
    tags: str = "",
    list_id: str = "",
    list_name: str = "",
    heading_id: str = "",
    heading: str = "",
    checklist_items: str = "",
    reveal: bool = False,
) -> str:
    """
    Create a new Things to-do via the Things URL scheme.

    Args:
        title: To-do title.
        when: Optional Things when value such as today, tomorrow, evening, anytime, someday, or a date.
        deadline: Optional deadline date.
        notes: Optional notes text.
        tags: Optional comma-separated tag titles.
        list_id: Optional target project or area ID.
        list_name: Optional target project or area title. Ignored if list_id is given.
        heading_id: Optional heading ID within the target project.
        heading: Optional heading title within the target project. Ignored if heading_id is given.
        checklist_items: Optional newline-separated checklist items.
        reveal: Set to true to reveal the new to-do in Things.

    Returns:
        The created to-do details including its ID when it can be resolved.
    """
    tool_id = _make_tool_id("things_create_todo")
    status_mgr = _status_manager()
    status_mgr.start_tool_call(tool_id, "things_create_todo", {"title": title})
    try:
        title = _strip(title)
        if not title:
            raise ValueError("A Things to-do title is required.")

        resolved_list_id = _resolve_project_or_area_id(list_id, list_name)
        resolved_heading_id = _resolve_heading_id(resolved_list_id, heading_id, heading)
        created_after = datetime.now().replace(microsecond=0)

        params: dict[str, Any] = {
            "title": title,
            "creation-date": _now_utc_iso(),
        }
        _set_if_present(params, "when", when)
        _set_if_present(params, "deadline", deadline)
        _set_if_present(params, "notes", notes)
        _set_if_present(params, "tags", tags)
        _set_if_present(params, "checklist-items", checklist_items)
        if resolved_list_id:
            params["list-id"] = resolved_list_id
        if resolved_heading_id:
            params["heading-id"] = resolved_heading_id
        if reveal:
            params["reveal"] = True

        _open_things_url("add", **params)
        item = _wait_for_recent_created_item(
            title=title,
            item_type="to-do",
            created_after=created_after,
            list_id=resolved_list_id,
        )
        if item is None:
            result = (
                "To-do created in Things, but the new item could not be resolved from the database yet."
            )
            status_mgr.complete_tool_call(tool_id, title[:30])
            return result

        result = "To-do created:\n\n" + _format_item(item)
        status_mgr.complete_tool_call(tool_id, title[:30])
        return result
    except Exception as exc:
        status_mgr.fail_tool_call(tool_id, str(exc)[:80])
        raise


@tool
def things_create_project(
    title: str,
    when: str = "",
    deadline: str = "",
    notes: str = "",
    tags: str = "",
    area_id: str = "",
    area: str = "",
    todos: str = "",
    reveal: bool = False,
) -> str:
    """
    Create a new Things project via the Things URL scheme.

    Args:
        title: Project title.
        when: Optional Things when value such as today, tomorrow, evening, anytime, someday, or a date.
        deadline: Optional deadline date.
        notes: Optional notes text.
        tags: Optional comma-separated tag titles.
        area_id: Optional target area ID.
        area: Optional target area title. Ignored if area_id is given.
        todos: Optional newline-separated to-do titles to seed the project with.
        reveal: Set to true to reveal the new project in Things.

    Returns:
        The created project details including its ID when it can be resolved.
    """
    tool_id = _make_tool_id("things_create_project")
    status_mgr = _status_manager()
    status_mgr.start_tool_call(tool_id, "things_create_project", {"title": title})
    try:
        title = _strip(title)
        if not title:
            raise ValueError("A Things project title is required.")

        resolved_area_id = _resolve_area_id(area_id or area)
        created_after = datetime.now().replace(microsecond=0)

        params: dict[str, Any] = {
            "title": title,
            "creation-date": _now_utc_iso(),
        }
        _set_if_present(params, "when", when)
        _set_if_present(params, "deadline", deadline)
        _set_if_present(params, "notes", notes)
        _set_if_present(params, "tags", tags)
        _set_if_present(params, "to-dos", todos)
        if resolved_area_id:
            params["area-id"] = resolved_area_id
        if reveal:
            params["reveal"] = True

        _open_things_url("add-project", **params)
        item = _wait_for_recent_created_item(
            title=title,
            item_type="project",
            created_after=created_after,
            area_id=resolved_area_id,
        )
        if item is None:
            result = (
                "Project created in Things, but the new item could not be resolved from the database yet."
            )
            status_mgr.complete_tool_call(tool_id, title[:30])
            return result

        result = "Project created:\n\n" + _format_item(item)
        status_mgr.complete_tool_call(tool_id, title[:30])
        return result
    except Exception as exc:
        status_mgr.fail_tool_call(tool_id, str(exc)[:80])
        raise


@tool
def things_update_todo(
    item_id: str,
    title: str = "",
    when: str = "",
    deadline: str = "",
    notes: str = "",
    append_notes: str = "",
    prepend_notes: str = "",
    tags: str = "",
    add_tags: str = "",
    list_id: str = "",
    list_name: str = "",
    heading_id: str = "",
    heading: str = "",
    checklist_items: str = "",
    append_checklist_items: str = "",
    prepend_checklist_items: str = "",
    reveal: bool = False,
) -> str:
    """
    Update or move an existing Things to-do.

    Args:
        item_id: The to-do ID.
        title: Replacement title. Leave empty to keep the current title.
        when: Replacement when value. Use CLEAR to remove it.
        deadline: Replacement deadline. Use CLEAR to remove it.
        notes: Replacement notes. Use CLEAR to clear notes.
        append_notes: Text to append to notes.
        prepend_notes: Text to prepend to notes.
        tags: Replacement comma-separated tags. Use CLEAR to clear all tags.
        add_tags: Comma-separated tags to add.
        list_id: Target project or area ID for moves.
        list_name: Target project or area title for moves. Ignored if list_id is given.
        heading_id: Target heading ID inside a project.
        heading: Target heading title inside a project. Ignored if heading_id is given.
        checklist_items: Replacement newline-separated checklist items. Use CLEAR to clear all checklist items.
        append_checklist_items: Checklist items to append.
        prepend_checklist_items: Checklist items to prepend.
        reveal: Set to true to reveal the updated to-do in Things.

    Returns:
        The updated to-do details.
    """
    tool_id = _make_tool_id("things_update_todo")
    status_mgr = _status_manager()
    status_mgr.start_tool_call(tool_id, "things_update_todo", {"item_id": item_id})
    try:
        item = _load_item(_strip(item_id), include_items=True)
        if item.get("type") != "to-do":
            raise ValueError("things_update_todo only works on Things to-dos.")

        resolved_list_id = _resolve_project_or_area_id(list_id, list_name)
        heading_project_id = resolved_list_id or item.get("project")
        resolved_heading_id = _resolve_heading_id(heading_project_id, heading_id, heading)

        params: dict[str, Any] = {}
        _set_if_present(params, "title", title)
        _set_if_present_or_clear(params, "when", when)
        _set_if_present_or_clear(params, "deadline", deadline)
        _set_if_present_or_clear(params, "notes", notes)
        _set_if_present(params, "append-notes", append_notes)
        _set_if_present(params, "prepend-notes", prepend_notes)
        _set_if_present_or_clear(params, "tags", tags)
        _set_if_present(params, "add-tags", add_tags)
        _set_if_present_or_clear(params, "checklist-items", checklist_items)
        _set_if_present(params, "append-checklist-items", append_checklist_items)
        _set_if_present(params, "prepend-checklist-items", prepend_checklist_items)
        if resolved_list_id:
            params["list-id"] = resolved_list_id
        if resolved_heading_id:
            params["heading-id"] = resolved_heading_id
        if reveal:
            params["reveal"] = True
        if not params:
            raise ValueError("No Things to-do fields were provided to update.")

        _open_things_url("update", uuid=item["uuid"], **params)
        updated = _wait_for_item(item["uuid"])
        result = "To-do updated:\n\n" + _format_item(updated)
        status_mgr.complete_tool_call(tool_id, updated.get("title", item_id)[:30])
        return result
    except Exception as exc:
        status_mgr.fail_tool_call(tool_id, str(exc)[:80])
        raise


@tool
def things_update_project(
    item_id: str,
    title: str = "",
    when: str = "",
    deadline: str = "",
    notes: str = "",
    append_notes: str = "",
    prepend_notes: str = "",
    tags: str = "",
    add_tags: str = "",
    area_id: str = "",
    area: str = "",
    reveal: bool = False,
) -> str:
    """
    Update or move an existing Things project.

    Args:
        item_id: The project ID.
        title: Replacement title. Leave empty to keep the current title.
        when: Replacement when value. Use CLEAR to remove it.
        deadline: Replacement deadline. Use CLEAR to remove it.
        notes: Replacement notes. Use CLEAR to clear notes.
        append_notes: Text to append to notes.
        prepend_notes: Text to prepend to notes.
        tags: Replacement comma-separated tags. Use CLEAR to clear all tags.
        add_tags: Comma-separated tags to add.
        area_id: Target area ID for moves.
        area: Target area title for moves. Ignored if area_id is given.
        reveal: Set to true to reveal the updated project in Things.

    Returns:
        The updated project details.
    """
    tool_id = _make_tool_id("things_update_project")
    status_mgr = _status_manager()
    status_mgr.start_tool_call(tool_id, "things_update_project", {"item_id": item_id})
    try:
        item = _load_item(_strip(item_id), include_items=True)
        if item.get("type") != "project":
            raise ValueError("things_update_project only works on Things projects.")

        resolved_area_id = _resolve_area_id(area_id or area)
        params: dict[str, Any] = {}
        _set_if_present(params, "title", title)
        _set_if_present_or_clear(params, "when", when)
        _set_if_present_or_clear(params, "deadline", deadline)
        _set_if_present_or_clear(params, "notes", notes)
        _set_if_present(params, "append-notes", append_notes)
        _set_if_present(params, "prepend-notes", prepend_notes)
        _set_if_present_or_clear(params, "tags", tags)
        _set_if_present(params, "add-tags", add_tags)
        if resolved_area_id:
            params["area-id"] = resolved_area_id
        if reveal:
            params["reveal"] = True
        if not params:
            raise ValueError("No Things project fields were provided to update.")

        _open_things_url("update-project", uuid=item["uuid"], **params)
        updated = _wait_for_item(item["uuid"])
        result = "Project updated:\n\n" + _format_item(updated)
        status_mgr.complete_tool_call(tool_id, updated.get("title", item_id)[:30])
        return result
    except Exception as exc:
        status_mgr.fail_tool_call(tool_id, str(exc)[:80])
        raise


@tool
def things_complete_item(item_id: str, completed: bool = True) -> str:
    """
    Mark a Things to-do or project complete or incomplete.

    Args:
        item_id: The to-do or project ID.
        completed: Set to true to mark complete, or false to mark incomplete.

    Returns:
        The updated item details.
    """
    tool_id = _make_tool_id("things_complete_item")
    status_mgr = _status_manager()
    status_mgr.start_tool_call(tool_id, "things_complete_item", {"item_id": item_id})
    try:
        item = _load_item(_strip(item_id), include_items=True)
        command = _update_command_for_item(item)
        _open_things_url(command, uuid=item["uuid"], completed=completed)
        updated = _wait_for_item(item["uuid"])
        result = "Item updated:\n\n" + _format_item(updated)
        status_mgr.complete_tool_call(tool_id, updated.get("title", item_id)[:30])
        return result
    except Exception as exc:
        status_mgr.fail_tool_call(tool_id, str(exc)[:80])
        raise


@tool
def things_cancel_item(item_id: str, canceled: bool = True) -> str:
    """
    Mark a Things to-do or project canceled or incomplete.

    Args:
        item_id: The to-do or project ID.
        canceled: Set to true to cancel, or false to mark incomplete.

    Returns:
        The updated item details.
    """
    tool_id = _make_tool_id("things_cancel_item")
    status_mgr = _status_manager()
    status_mgr.start_tool_call(tool_id, "things_cancel_item", {"item_id": item_id})
    try:
        item = _load_item(_strip(item_id), include_items=True)
        command = _update_command_for_item(item)
        _open_things_url(command, uuid=item["uuid"], canceled=canceled)
        updated = _wait_for_item(item["uuid"])
        result = "Item updated:\n\n" + _format_item(updated)
        status_mgr.complete_tool_call(tool_id, updated.get("title", item_id)[:30])
        return result
    except Exception as exc:
        status_mgr.fail_tool_call(tool_id, str(exc)[:80])
        raise
