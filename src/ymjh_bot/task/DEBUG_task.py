"""用于测试账号角色切换的最小队列任务。"""

from botCore import GameTask, step


class DebugTask(GameTask):
    """等待十秒后完成，不与游戏交互。"""

    task_key = "DEBUG"
    task_name = "调试任务（等待 10 秒）"
    task_description = "用于测试角色切换；等待 10 秒后完成任务"

    @step(retry=0, timeout_ms=15000)
    def wait_ten_seconds(self) -> None:
        """等待十秒，以便在继续前观察当前角色。"""
        self._log("调试任务开始，等待 10 秒")
        self.wait(10_000)
        self._log("调试任务完成")
