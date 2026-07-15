"""
一梦江湖启动任务 - Python DSL 实现

原 YAML 版本已移除，当前文件是唯一任务定义。
"""

from botCore import step

from ymjh_bot.ym_game_task import YmGameTask


class StartTask(YmGameTask):
    """一梦江湖启动任务。"""

    task_key = "QDYX"
    task_name = "启动游戏"
    task_description = "启动游戏任务"
    task_visible = False
    auto_ensure_game_started = False
    auto_recover_health = False
    STARTUP_LOG_DISPLAY_NAME = "一梦江湖启动"

    @step(retry=0, timeout_ms=360000)
    def start_game(self) -> None:
        """启动一梦江湖游戏。"""
        self.ensure_game_started(force=True)

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"启动任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
