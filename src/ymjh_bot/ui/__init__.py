"""UI components for ymjh_bot."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .task_queue_window import TaskQueueWindow

__all__ = ["TaskQueueWindow"]


def __getattr__(name: str):
    """Import the Qt window lazily so state helpers remain headless-safe."""
    if name == "TaskQueueWindow":
        from .task_queue_window import TaskQueueWindow

        return TaskQueueWindow
    raise AttributeError(name)
