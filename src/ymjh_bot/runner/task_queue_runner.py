"""任务队列执行器 - 支持多任务顺序执行和暂停/继续功能。"""

from __future__ import annotations

import time
from typing import Any, Callable

from botCore import ADBClient, VisionEngine, RunLogger, ExecutionResult, GameTask
from botCore.execution import DslStepExecutor, resolve_step_jump


class TaskQueueRunner:
    """任务队列执行器。

    Usage:
        runner = TaskQueueRunner(task_list, adb, vision, logger)
        runner.run()  # 执行所有任务
        runner.pause()  # 暂停
        runner.resume()  # 继续
        runner.stop()  # 停止
    """

    def __init__(
        self,
        task_list: list[GameTask],
        adb_client: ADBClient,
        vision: VisionEngine,
        *,
        logger: RunLogger | None = None,
        event_callback: Callable[[str], None] | None = None,
        progress_callback: Callable[[dict[str, int]], None] | None = None,
    ):
        self.task_list = task_list
        self.adb = adb_client
        self.vision = vision
        self.logger = logger
        self.event_callback = event_callback
        self.progress_callback = progress_callback
        self._stop_requested = False
        self._paused = False

        # 进度跟踪
        self.current_task_index = 0
        self.current_step_index = 0
        self.total_tasks = len(task_list)
        self._started_task_index: int | None = None
        self._last_failure_message: str | None = None
        self._executor = DslStepExecutor(
            should_stop=lambda: self._stop_requested or self._paused,
            emit=self._emit,
        )

    def stop(self) -> None:
        """停止任务队列。"""
        self._stop_requested = True
        for task in self.task_list:
            task.stop()
        self._emit_progress()

    def pause(self) -> None:
        """暂停任务队列（保持当前进度）。"""
        self._paused = True
        # 只设置当前正在执行的任务为停止状态（如果有的话）
        if 0 <= self.current_task_index < len(self.task_list):
            self.task_list[self.current_task_index].stop()
        self._emit_progress()

    def resume(self) -> None:
        """继续执行任务队列。"""
        self._paused = False
        # 重置当前任务的停止状态，以便继续执行
        if 0 <= self.current_task_index < len(self.task_list):
            self.task_list[self.current_task_index]._stop_requested = False

    def is_paused(self) -> bool:
        """检查是否暂停。"""
        return self._paused

    def get_progress(self) -> dict[str, int]:
        """Return a serializable snapshot of the current queue position."""
        return {
            "current_task_index": self.current_task_index,
            "current_step_index": self.current_step_index,
        }

    def load_progress(self, progress: dict[str, Any] | None) -> None:
        """Restore queue position from a saved progress dictionary."""
        if not progress:
            self.current_task_index = 0
            self.current_step_index = 0
            self._started_task_index = None
            self._emit_progress()
            return

        try:
            task_index = int(progress.get("current_task_index", 0))
            step_index = int(progress.get("current_step_index", 0))
        except (TypeError, ValueError):
            task_index = 0
            step_index = 0

        task_index = max(0, min(task_index, self.total_tasks))
        if task_index >= self.total_tasks:
            step_index = 0
        else:
            step_count = len(self.task_list[task_index].get_steps())
            if step_count <= 0:
                step_index = 0
            else:
                step_index = max(0, min(step_index, step_count - 1))

        self.current_task_index = task_index
        self.current_step_index = step_index
        self._started_task_index = None
        self._emit_progress()

    def run(self) -> list[ExecutionResult]:
        """执行任务队列中的所有任务。

        Returns:
            所有任务的执行结果列表
        """
        self._stop_requested = False
        self._paused = False
        self._last_failure_message = None
        self._emit_progress()
        self.adb.ensure_device()

        screen_size = self.adb.get_screen_size()
        self._emit(f"Connected to {self.adb.serial}, resolution={screen_size}")

        # Verify screenshot matches wm size
        test_shot = self.adb.screenshot()
        h, w = test_shot.shape[:2]
        self._emit(f"Screenshot size: {w}x{h}, wm size: {screen_size[0]}x{screen_size[1]}")

        if (w, h) != screen_size:
            self._emit(f"WARNING: Resolution mismatch! Using screenshot size {w}x{h}")
            screen_size = (w, h)

        all_results: list[ExecutionResult] = []

        while self.current_task_index < self.total_tasks:
            # 检查停止请求
            if self._stop_requested:
                self._emit("任务队列已停止")
                break

            # 检查暂停
            while self._paused:
                if self._stop_requested:
                    break
                time.sleep(0.1)
            if self._stop_requested:
                break

            task = self.task_list[self.current_task_index]
            task_name = getattr(task, "task_name", task.__class__.__name__)

            self._emit(f">>> 开始执行任务 {self.current_task_index + 1}/{self.total_tasks}: {task_name}")

            # 设置任务运行时依赖
            task._screen_resolution = getattr(task, "FIXED_RESOLUTION", task.design_resolution)
            task.setup(self.adb, self.vision, self.logger, self.event_callback)

            # 执行单个任务
            task_results, task_completed = self._run_single_task(task)
            all_results.extend(task_results)

            if self._stop_requested:
                break
            if self._paused:
                continue
            if not task_completed:
                if self._last_failure_message:
                    raise RuntimeError(self._last_failure_message)
                break

            # 任务完成后，更新索引
            self.current_task_index += 1
            self.current_step_index = 0
            self._started_task_index = None
            self._emit_progress()

        # 所有任务完成后
        if self._stop_requested:
            self._emit(f"任务队列已停止，完成 {self.current_task_index}/{self.total_tasks} 个任务")
        else:
            self._emit("任务队列执行完成")

        return all_results

    def _run_single_task(self, task: GameTask) -> tuple[list[ExecutionResult], bool]:
        """执行单个任务。

        Args:
            task: 要执行的任务实例

        Returns:
            任务的执行结果列表
        """
        results: list[ExecutionResult] = []
        steps = task.get_steps()
        loop_count = max(1, task.loop_count)
        task_name = getattr(task, "task_name", task.__class__.__name__)

        # 调用任务启动钩子（只在第一次 loop 调用）
        if self._started_task_index != self.current_task_index:
            if hasattr(task, "before_start"):
                task.before_start()
            if hasattr(task, "on_start"):
                task.on_start()
        self._started_task_index = self.current_task_index

        for round_idx in range(loop_count):
            if self._stop_requested or self._paused:
                return results, False

            self._emit(f"  Loop {round_idx + 1}/{loop_count}")

            # 从保存的 step_index 继续（支持暂停/继续）
            step_index = self.current_step_index if round_idx == 0 else 0
            while step_index < len(steps):
                if self._stop_requested or self._paused:
                    # 保存当前步骤索引
                    self.current_step_index = step_index
                    self._emit_progress()
                    return results, False

                step_name, step_func, step_meta = steps[step_index]
                task._current_step_index = step_index
                self.current_step_index = step_index
                self._emit_progress()

                if not step_meta.get("enabled", True):
                    step_index += 1
                    self.current_step_index = step_index
                    continue

                result = self._execute_step(step_name, step_func, step_meta)

                if self._paused or self._stop_requested:
                    self.current_step_index = step_index
                    self._emit_progress()
                    return results, False

                results.append(result)

                if self.logger:
                    self.logger.log_step_result(step_name, result)

                self._emit(
                    f"    [{step_name}] {'OK' if result.success else 'FAIL'} - "
                    f"{result.reason} ({result.elapsed_ms} ms)"
                )

                if not result.success:
                    self.current_step_index = step_index
                    self._last_failure_message = (
                        f"任务 {task_name} 步骤 {step_name} 执行失败：{result.reason}"
                    )
                    self._emit(f"    {self._last_failure_message}，队列停止")
                    self._emit_progress()
                    return results, False

                # 检查跳转请求
                if task._jump_target:
                    target = task._jump_target
                    task._jump_target = None

                    jump = resolve_step_jump(target, steps, step_index)
                    if jump.message:
                        self._emit(f"    {jump.message}")
                    if jump.end_loop:
                        break
                    step_index = jump.next_index
                    self.current_step_index = step_index
                    continue

                step_index += 1
                self.current_step_index = step_index

                # 应用间隔
                interval_ms = step_meta.get("interval_ms") or task._default_interval_ms
                if interval_ms is not None and interval_ms > 0:
                    time.sleep(interval_ms / 1000.0)

            # 重置 step_index 为 0，以便下一个 loop 从头开始
            if not self._paused and not self._stop_requested:
                self.current_step_index = 0

        # 调用 on_finish
        if hasattr(task, "on_finish") and not self._paused and not self._stop_requested:
            task.on_finish(results)

        return results, not self._paused and not self._stop_requested

    def _execute_step(
        self,
        name: str,
        func: Callable[[GameTask], object],
        meta: dict,
    ) -> ExecutionResult:
        """执行单个步骤。"""
        return self._executor.execute(
            self.task_list[self.current_task_index],
            name,
            func,
            meta,
        )

    def _emit(self, message: str) -> None:
        """发送事件消息。"""
        if self.event_callback:
            self.event_callback(message)

    def _emit_progress(self) -> None:
        """Send the current progress snapshot to the UI/state layer."""
        if self.progress_callback:
            self.progress_callback(self.get_progress())
