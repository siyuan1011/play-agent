"""Minimal queue task for testing account-role switching."""

from botCore import GameTask, step


class DebugTask(GameTask):
    """Wait for ten seconds, then complete without interacting with the game."""

    task_key = "DEBUG"
    task_name = "调试任务（等待 10 秒）"
    task_description = "用于测试角色切换；等待 10 秒后完成任务"

    @step(retry=0, timeout_ms=15000)
    def wait_ten_seconds(self) -> None:
        """Wait ten seconds so the current role is observable before advancing."""
        self._log("调试任务开始，等待 10 秒")
        self.wait(10_000)
        self._log("调试任务完成")
