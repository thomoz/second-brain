"""
Asana Direct Integration for Second Brain.

Uses Asana Python SDK v5 with Personal Access Token authentication.

Usage:
    uv run python -m integrations.asana_api my-tasks --max 10
    uv run python -m integrations.asana_api project <project_id>
    uv run python -m integrations.asana_api overdue
    uv run python -m integrations.asana_api due-soon --days 3
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# Add parent dir for config imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import ASANA_ACCESS_TOKEN, ASANA_WORKSPACE_ID, ASANA_PROJECT_ID, ASANA_USERS  # noqa: E402
from sanitize import sanitize_external_text  # noqa: E402
from shared import with_retry  # noqa: E402


@dataclass
class AsanaTask:
    """Represents an Asana task."""

    gid: str
    name: str
    due_on: date | None = None
    completed: bool = False
    assignee: str | None = None
    project: str | None = None
    notes: str | None = None


def get_asana_client() -> Any:
    """Create authenticated Asana API client (v5 SDK)."""
    import asana  # type: ignore[import-untyped]

    if not ASANA_ACCESS_TOKEN:
        raise ValueError(
            "ASANA_ACCESS_TOKEN not set in .env\n"
            "Get a Personal Access Token from https://app.asana.com/0/developer-console"
        )

    configuration = asana.Configuration()
    configuration.access_token = ASANA_ACCESS_TOKEN
    client: Any = asana.ApiClient(configuration)
    return client


def _parse_task(task_data: Any) -> AsanaTask:
    """Parse an Asana task response into AsanaTask dataclass."""
    # v5 SDK returns objects with attributes or dicts depending on context
    if isinstance(task_data, dict):
        data = task_data
    else:
        data = task_data.to_dict() if hasattr(task_data, "to_dict") else vars(task_data)

    due_on_val: date | None = None
    due_str = data.get("due_on")
    if due_str and isinstance(due_str, str):
        due_on_val = datetime.strptime(due_str, "%Y-%m-%d").date()
    elif isinstance(due_str, date):
        due_on_val = due_str

    assignee_name: str | None = None
    assignee_data = data.get("assignee")
    if isinstance(assignee_data, dict):
        assignee_name = assignee_data.get("name")
    elif assignee_data is not None and hasattr(assignee_data, "name"):
        assignee_name = assignee_data.name

    project_name: str | None = None
    projects_data = data.get("projects")
    if projects_data and isinstance(projects_data, list) and len(projects_data) > 0:
        first_proj = projects_data[0]
        if isinstance(first_proj, dict):
            project_name = first_proj.get("name")
        elif first_proj is not None and hasattr(first_proj, "name"):
            project_name = first_proj.name

    notes_raw = data.get("notes", "")
    notes_val = str(notes_raw)[:200] if notes_raw else None

    return AsanaTask(
        gid=str(data.get("gid", "")),
        name=str(data.get("name", "")),
        due_on=due_on_val,
        completed=bool(data.get("completed", False)),
        assignee=assignee_name,
        project=project_name,
        notes=notes_val,
    )


def resolve_assignee(name: str | None) -> str:
    """Resolve a friendly name to an Asana GID, or return 'me'."""
    if not name:
        return "me"
    key = name.lower().strip()
    if key in ASANA_USERS:
        return ASANA_USERS[key]
    # If it looks like a raw GID, pass through
    if key.isdigit():
        return key
    raise ValueError(
        f"Unknown Asana user '{name}'. Known users: {', '.join(ASANA_USERS.keys())}"
    )


def get_my_tasks(
    max_results: int = 20,
    only_incomplete: bool = True,
    assignee: str | None = None,
) -> list[AsanaTask]:
    """
    Get tasks assigned to a user in the configured workspace.

    Uses v5 SDK: TasksApi.get_tasks() with assignee + workspace.
    Pass assignee as a friendly name ('teamname'), GID, or None for 'me'.
    """
    import asana

    api_client = get_asana_client()
    tasks_api = asana.TasksApi(api_client)

    opts: dict[str, Any] = {
        "assignee": resolve_assignee(assignee),
        "workspace": ASANA_WORKSPACE_ID,
        "opt_fields": "name,due_on,completed,assignee.name,notes,projects.name",
    }
    if only_incomplete:
        opts["completed_since"] = "now"

    result: list[AsanaTask] = []
    try:
        tasks = with_retry(lambda: tasks_api.get_tasks(opts))
        for task_data in tasks:
            if len(result) >= max_results:
                break
            task = _parse_task(task_data)
            if only_incomplete and task.completed:
                continue
            result.append(task)
    except Exception as e:
        print(f"Error fetching Asana tasks: {e}")

    return result


def get_project_tasks(
    project_gid: str | None = None,
    only_incomplete: bool = True,
    max_results: int = 20,
) -> list[AsanaTask]:
    """Get tasks from a specific project."""
    import asana

    api_client = get_asana_client()
    tasks_api = asana.TasksApi(api_client)

    gid = project_gid or ASANA_PROJECT_ID

    opts: dict[str, Any] = {
        "project": gid,
        "opt_fields": "name,due_on,completed,assignee.name,notes",
    }
    if only_incomplete:
        opts["completed_since"] = "now"

    result: list[AsanaTask] = []
    try:
        tasks = with_retry(lambda: tasks_api.get_tasks(opts))
        for task_data in tasks:
            if len(result) >= max_results:
                break
            task = _parse_task(task_data)
            if only_incomplete and task.completed:
                continue
            result.append(task)
    except Exception as e:
        print(f"Error fetching project tasks: {e}")

    return result


def search_tasks(
    due_before: date | None = None,
    due_after: date | None = None,
    completed: bool = False,
    max_results: int = 100,
    assignee: str | None = None,
) -> list[AsanaTask]:
    """Search tasks using Asana's server-side Search API.

    Uses /workspaces/{gid}/tasks/search for efficient filtering by due date
    and completion status. Requires Asana Premium.

    Falls back to get_my_tasks() with client-side filtering if search API
    is unavailable (non-premium workspace).
    """
    import asana

    api_client = get_asana_client()
    tasks_api = asana.TasksApi(api_client)

    resolved = resolve_assignee(assignee)

    # v5 SDK: search_tasks_for_workspace(workspace_gid, opts) — opts is positional
    # Dot-notation params (due_on.before, assignee.any) go into opts dict
    opts: dict[str, Any] = {
        "opt_fields": "name,due_on,completed,assignee.name,notes,projects.name",
        "assignee.any": resolved,
        "completed": completed,
    }
    if due_before:
        opts["due_on.before"] = due_before.isoformat()
    if due_after:
        opts["due_on.after"] = due_after.isoformat()

    result: list[AsanaTask] = []
    try:
        tasks = with_retry(
            lambda: tasks_api.search_tasks_for_workspace(
                ASANA_WORKSPACE_ID,
                opts,
            )
        )
        for task_data in tasks:
            if len(result) >= max_results:
                break
            task = _parse_task(task_data)
            result.append(task)
    except Exception as e:
        error_str = str(e)
        if "402" in error_str or "Payment Required" in error_str:
            print("Asana Search API requires Premium — falling back to client-side filtering")
            return _fallback_search(due_before, due_after, completed, max_results, assignee)
        print(f"Error searching Asana tasks: {e}")
    return result


def _fallback_search(
    due_before: date | None,
    due_after: date | None,
    completed: bool,
    max_results: int,
    assignee: str | None = None,
) -> list[AsanaTask]:
    """Client-side filtering fallback if Search API is unavailable."""
    tasks = get_my_tasks(max_results=200, only_incomplete=not completed, assignee=assignee)
    result: list[AsanaTask] = []
    for t in tasks:
        if not t.due_on:
            continue
        if due_before and t.due_on >= due_before:
            continue
        if due_after and t.due_on < due_after:
            continue
        result.append(t)
        if len(result) >= max_results:
            break
    return result


def complete_task(task_gid: str) -> AsanaTask:
    """Mark a task as complete in Asana."""
    import asana

    api_client = get_asana_client()
    tasks_api = asana.TasksApi(api_client)

    body = {"data": {"completed": True}}
    result = with_retry(lambda: tasks_api.update_task(body, task_gid, {}))
    return _parse_task(result)


def create_task(
    name: str,
    due_on: str | None = None,
    assignee: str | None = None,
    project: str | None = None,
    notes: str | None = None,
    section: str | None = None,
    parent: str | None = None,
) -> AsanaTask:
    """Create a new task in Asana.

    Args:
        name: Task name/title.
        due_on: Due date as YYYY-MM-DD string, or None.
        assignee: Friendly name, GID, or None for 'me'.
        project: Project GID to add the task to, or None.
        notes: Task description/notes, or None.
        section: Section GID to place the task in, or None.
        parent: Parent task GID for creating a subtask, or None.
    """
    import asana

    api_client = get_asana_client()
    tasks_api = asana.TasksApi(api_client)

    data: dict[str, Any] = {
        "name": name,
        "workspace": ASANA_WORKSPACE_ID,
        "assignee": resolve_assignee(assignee),
    }
    if due_on:
        data["due_on"] = due_on
    if notes:
        data["notes"] = notes
    if project:
        data["projects"] = [project]
    if parent:
        data["parent"] = parent

    body = {"data": data}
    opts = {"opt_fields": "name,due_on,completed,assignee.name,notes,projects.name"}
    result = with_retry(lambda: tasks_api.create_task(body, opts))
    task = _parse_task(result)

    # Move to section if specified, auto-ordering by due date
    if section:
        add_task_to_section(task.gid, section, auto_order_date=task.due_on)

    return task


def add_comment(task_gid: str, text: str) -> str:
    """Add a comment (story) to an Asana task.

    Returns the GID of the created comment.
    """
    import asana

    api_client = get_asana_client()
    stories_api = asana.StoriesApi(api_client)

    body = {"data": {"text": text}}
    result = with_retry(lambda: stories_api.create_story_for_task(body, task_gid, {}))

    # Result is a story object — extract what we need
    if isinstance(result, dict):
        return result.get("gid", "")
    elif hasattr(result, "gid"):
        return result.gid
    return str(result)


def get_sections(project_gid: str | None = None) -> list[dict[str, str]]:
    """Get all sections in a project.

    Returns a list of dicts with 'gid' and 'name' keys.
    """
    import asana

    api_client = get_asana_client()
    sections_api = asana.SectionsApi(api_client)

    gid = project_gid or ASANA_PROJECT_ID
    result: list[dict[str, str]] = []
    try:
        sections = with_retry(
            lambda: sections_api.get_sections_for_project(gid, {"opt_fields": "name"})
        )
        for section in sections:
            data = section.to_dict() if hasattr(section, "to_dict") else section
            result.append({"gid": str(data.get("gid", "")), "name": str(data.get("name", ""))})
    except Exception as e:
        print(f"Error fetching sections: {e}")
    return result


def get_section_tasks(
    section_gid: str,
    only_incomplete: bool = True,
    max_results: int = 50,
) -> list[AsanaTask]:
    """Get tasks in a specific section."""
    import asana

    api_client = get_asana_client()
    tasks_api = asana.TasksApi(api_client)

    opts: dict[str, Any] = {
        "section": section_gid,
        "opt_fields": "name,due_on,completed,assignee.name,notes,projects.name",
    }
    if only_incomplete:
        opts["completed_since"] = "now"

    result: list[AsanaTask] = []
    try:
        tasks = with_retry(lambda: tasks_api.get_tasks(opts))
        for task_data in tasks:
            if len(result) >= max_results:
                break
            task = _parse_task(task_data)
            if only_incomplete and task.completed:
                continue
            result.append(task)
    except Exception as e:
        print(f"Error fetching section tasks: {e}")
    return result


def _find_insert_after_by_date(
    section_gid: str,
    target_date: date,
) -> str | None:
    """Find the task GID to insert after to maintain chronological order.

    Walks the section's tasks and returns the GID of the last task whose
    due date is <= target_date.  Returns None if the new task should go
    at the top (earlier than everything).
    """
    tasks = get_section_tasks(section_gid, only_incomplete=True, max_results=200)
    insert_after: str | None = None
    for t in tasks:
        if t.due_on is None or t.due_on <= target_date:
            insert_after = t.gid
        else:
            break
    return insert_after


def add_task_to_section(
    task_gid: str,
    section_gid: str,
    insert_after: str | None = None,
    insert_before: str | None = None,
    auto_order_date: date | None = None,
) -> None:
    """Add/move a task to a section within a project.

    Args:
        task_gid: The task to move.
        section_gid: The section to move it into.
        insert_after: Task GID to insert after (for ordering).
        insert_before: Task GID to insert before (for ordering).
        auto_order_date: If set (and insert_after/before are None),
            automatically find the right position based on due date.
    """
    import asana

    # Auto-find insertion point if no explicit ordering given
    if not insert_after and not insert_before and auto_order_date:
        insert_after = _find_insert_after_by_date(section_gid, auto_order_date)

    api_client = get_asana_client()
    sections_api = asana.SectionsApi(api_client)

    data: dict[str, Any] = {"task": task_gid}
    if insert_after:
        data["insert_after"] = insert_after
    if insert_before:
        data["insert_before"] = insert_before

    opts: dict[str, Any] = {"body": {"data": data}}
    with_retry(lambda: sections_api.add_task_for_section(section_gid, opts))


def move_task(
    task_gid: str,
    to_project: str,
    from_project: str | None = None,
    insert_after: str | None = None,
) -> None:
    """Move a task to a different project (add to new, remove from old).

    Args:
        task_gid: The task to move.
        to_project: Project GID to move the task into.
        from_project: Project GID to remove the task from (optional).
        insert_after: Task GID to insert after for ordering (optional).
    """
    import requests as _requests

    headers = {"Authorization": f"Bearer {ASANA_ACCESS_TOKEN}"}

    # Add to new project
    add_data: dict[str, Any] = {"project": to_project}
    if insert_after:
        add_data["insert_after"] = insert_after
    _requests.post(
        f"https://app.asana.com/api/1.0/tasks/{task_gid}/addProject",
        headers=headers,
        json={"data": add_data},
    ).raise_for_status()

    # Remove from old project
    if from_project:
        _requests.post(
            f"https://app.asana.com/api/1.0/tasks/{task_gid}/removeProject",
            headers=headers,
            json={"data": {"project": from_project}},
        ).raise_for_status()


def search_tasks_by_text(
    query: str,
    max_results: int = 20,
    assignee: str | None = None,
) -> list[AsanaTask]:
    """Search tasks by text query using Asana's Search API.

    Searches task names and notes for the given query string.
    Falls back to client-side filtering if search API is unavailable.
    """
    import asana

    api_client = get_asana_client()
    tasks_api = asana.TasksApi(api_client)

    opts: dict[str, Any] = {
        "opt_fields": "name,due_on,completed,assignee.name,notes,projects.name",
        "text": query,
        "completed": False,
    }
    if assignee:
        resolved = resolve_assignee(assignee)
        opts["assignee.any"] = resolved

    result: list[AsanaTask] = []
    try:
        tasks = with_retry(
            lambda: tasks_api.search_tasks_for_workspace(
                ASANA_WORKSPACE_ID,
                opts,
            )
        )
        for task_data in tasks:
            if len(result) >= max_results:
                break
            task = _parse_task(task_data)
            result.append(task)
    except Exception as e:
        error_str = str(e)
        if "402" in error_str or "Payment Required" in error_str:
            # Fallback: get all tasks and filter client-side
            all_tasks = get_my_tasks(max_results=100, assignee=assignee)
            q_lower = query.lower()
            for t in all_tasks:
                if q_lower in t.name.lower() or (t.notes and q_lower in t.notes.lower()):
                    result.append(t)
                    if len(result) >= max_results:
                        break
        else:
            print(f"Error searching Asana tasks: {e}")
    return result


def get_overdue_tasks(assignee: str | None = None) -> list[AsanaTask]:
    """Get incomplete tasks that are past their due date (server-side filtering)."""
    today = date.today()
    return search_tasks(due_before=today, completed=False, assignee=assignee)


def get_due_soon_tasks(days: int = 3, assignee: str | None = None) -> list[AsanaTask]:
    """Get incomplete tasks due within N days (server-side filtering)."""
    today = date.today()
    deadline = today + timedelta(days=days)
    return search_tasks(due_after=today, due_before=deadline, completed=False, assignee=assignee)


def format_tasks_for_context(tasks: list[AsanaTask]) -> str:
    """Format tasks for inclusion in Claude's context prompt."""
    if not tasks:
        return "No tasks found."

    output: list[str] = []
    for task in tasks:
        due_str = task.due_on.strftime("%Y-%m-%d, %A") if task.due_on else "No due date"

        entry = f"- **{sanitize_external_text(task.name, 'asana')}** (GID: {task.gid})"
        entry += f"\n  Due: {due_str}"
        if task.project:
            entry += f" | Project: {sanitize_external_text(task.project, 'asana')}"
        if task.notes:
            entry += f"\n  Notes: {sanitize_external_text(task.notes[:100], 'asana')}..."

        output.append(entry)

    return "\n\n".join(output)


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Asana integration (v5 SDK)")
    parser.add_argument("command", choices=["my-tasks", "project", "overdue", "due-soon"])
    parser.add_argument("project_gid", nargs="?", default=None, help="Project GID for project cmd")
    parser.add_argument("--max", type=int, default=20)
    parser.add_argument("--days", type=int, default=3)

    args = parser.parse_args()

    if args.command == "my-tasks":
        task_list = get_my_tasks(max_results=args.max)
    elif args.command == "project":
        task_list = get_project_tasks(project_gid=args.project_gid, max_results=args.max)
    elif args.command == "overdue":
        task_list = get_overdue_tasks()
    elif args.command == "due-soon":
        task_list = get_due_soon_tasks(days=args.days)

    print(format_tasks_for_context(task_list))
