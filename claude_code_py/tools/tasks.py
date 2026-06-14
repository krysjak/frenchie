from __future__ import annotations

from typing import Any

from claude_code_py.services.shell_task_store import SHELL_TASK_TYPE, ShellTaskStore
from claude_code_py.services.task_store import TaskStore


def _store() -> TaskStore:
    return TaskStore()


def task_create(subject: str, description: str, activeForm: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    task = _store().create(subject, description, activeForm, metadata)
    return {"task": {"id": task.id, "subject": task.subject}}


def task_get(taskId: str) -> dict[str, Any]:
    task = _store().get(taskId)
    if not task:
        return {"task": None}
    if task.metadata.get("type") == SHELL_TASK_TYPE:
        return {"task": ShellTaskStore().summarize(task)}
    return {
        "task": {
            "id": task.id,
            "subject": task.subject,
            "description": task.description,
            "status": task.status,
            "blocks": task.blocks,
            "blockedBy": task.blockedBy,
        }
    }


def task_list() -> dict[str, Any]:
    shell_store = ShellTaskStore()
    tasks = []
    for task in _store().list():
        if task.metadata.get("_internal"):
            continue
        task = shell_store.refresh(task)
        tasks.append(
            {
                "id": task.id,
                "subject": task.subject,
                "status": task.status,
                "owner": task.owner,
                "blockedBy": task.blockedBy,
                "type": task.metadata.get("type"),
                "pid": task.metadata.get("pid"),
            }
        )
    completed = {task["id"] for task in tasks if task["status"] == "completed"}
    for task in tasks:
        task["blockedBy"] = [task_id for task_id in task["blockedBy"] if task_id not in completed]
    return {"tasks": tasks}


def task_update(taskId: str, **updates: Any) -> dict[str, Any]:
    existing = _store().get(taskId)
    task, changed = _store().update(taskId, **updates)
    if not task:
        return {"success": False, "taskId": taskId, "updatedFields": [], "error": "Task not found"}
    status_change = None
    if existing and updates.get("status") and updates.get("status") != existing.status:
        status_change = {"from": existing.status, "to": updates.get("status")}
    return {"success": True, "taskId": taskId, "updatedFields": changed, "statusChange": status_change}


def task_stop(task_id: str | None = None, shell_id: str | None = None) -> dict[str, Any]:
    task_id = task_id or shell_id
    if not task_id:
        raise ValueError("Missing required parameter: task_id")
    task = _store().get(task_id)
    if task and task.metadata.get("type") == SHELL_TASK_TYPE:
        stopped = ShellTaskStore().stop(task_id)
        if not stopped:
            raise ValueError(f"No task found with ID: {task_id}")
        return {"message": f"Successfully stopped task: {stopped.id}", "task_id": stopped.id, "task_type": SHELL_TASK_TYPE, "command": stopped.subject}
    task, changed = _store().update(task_id, status="cancelled")
    if not task:
        raise ValueError(f"No task found with ID: {task_id}")
    return {"message": f"Successfully stopped task: {task.id}", "task_id": task.id, "task_type": "local", "command": task.subject}
