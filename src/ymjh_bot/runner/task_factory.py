"""Create fresh configured task objects for each account role."""

from __future__ import annotations

from typing import Any

from botCore import GameTask
from ymjh_bot.ui.task_queue_state import (
    HSLJ_TASK_KEY,
    SHRW_TASK_KEY,
    normalize_hslj_settings,
    normalize_shrw_settings,
)


def create_task_instances(
    selected_tasks: list[dict[str, Any]],
    settings: dict[str, Any],
) -> list[GameTask]:
    """Build a clean task list while preserving queue order and settings."""
    instances: list[GameTask] = []
    for task_info in selected_tasks:
        task_class = task_info["class"]
        task_key = str(task_info.get("key") or "")
        if task_key == HSLJ_TASK_KEY:
            instances.append(
                task_class(
                    hslj_settings=normalize_hslj_settings(settings.get(HSLJ_TASK_KEY)),
                )
            )
        elif task_key == SHRW_TASK_KEY:
            instances.append(
                task_class(
                    shrw_settings=normalize_shrw_settings(settings.get(SHRW_TASK_KEY)),
                )
            )
        else:
            instances.append(task_class())
    return instances
