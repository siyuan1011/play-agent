"""Create fresh configured task objects for each account role."""

from __future__ import annotations

from typing import Any

from botCore import GameTask
from ymjh_bot.ui.task_queue_state import (
    HSLJ_TASK_KEY,
    RCGM_TASK_KEY,
    SHRW_TASK_KEY,
    normalize_hslj_settings,
    normalize_rcgm_settings,
    normalize_shrw_settings,
)


def create_task_instances(
    selected_tasks: list[dict[str, Any]],
    settings: dict[str, Any],
) -> list[GameTask]:
    """按角色创建独立任务，保留队列顺序和配置。

    参数：
        selected_tasks：按运行顺序排列的任务类及元数据。
        settings：各任务键对应的已保存配置。
    """
    instances: list[GameTask] = []  # 为当前角色创建的独立任务实例列表。
    for task_info in selected_tasks:  # 当前队列项的任务类与配置键。
        task_class = task_info["class"]  # 当前队列项的可加载任务类。
        task_key = str(task_info.get("key") or "")  # 当前任务的持久化配置键。
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
        elif task_key == RCGM_TASK_KEY:
            instances.append(
                task_class(
                    rcgm_settings=normalize_rcgm_settings(settings.get(RCGM_TASK_KEY)),
                )
            )
        else:
            instances.append(task_class())
    return instances
