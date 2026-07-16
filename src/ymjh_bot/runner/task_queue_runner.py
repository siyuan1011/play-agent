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

    MAX_TASK_ATTEMPTS = 3

    def __init__(
        self,
        task_list: list[GameTask],
        adb_client: ADBClient,
        vision: VisionEngine,
        *,
        logger: RunLogger | None = None,
        event_callback: Callable[[str], None] | None = None,
        progress_callback: Callable[[dict[str, int]], None] | None = None,
        verbose: bool = False,
    ):
        self.task_list = task_list
        self.adb = adb_client
        self.vision = vision
        self.logger = logger
        self.event_callback = event_callback
        self.progress_callback = progress_callback
        self.verbose = verbose
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

            # 设置任务运行时依赖
            task._screen_resolution = getattr(task, "FIXED_RESOLUTION", task.design_resolution)
            task.setup(
                self.adb,
                self.vision,
                self.logger,
                self.event_callback,
                verbose=self.verbose,
            )

            # 执行当前任务，失败时从头重试，最多执行 MAX_TASK_ATTEMPTS 次。
            task_results, task_completed = self._run_task_with_retries(task)
            all_results.extend(task_results)

            if self._stop_requested:
                break
            if self._paused:
                continue

            if not task_completed:
                self._emit("当前任务已跳过，继续执行下一个任务")

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

    def _run_task_with_retries(self, task: GameTask) -> tuple[list[ExecutionResult], bool]:
        """执行当前任务，失败时在当前进程内从头重试。"""
        results: list[ExecutionResult] = []
        task_name = getattr(task, "task_name", task.__class__.__name__)
        attempt = 1

        self._emit_task_attempt_start(task_name, attempt)
        while attempt <= self.MAX_TASK_ATTEMPTS:
            task_results, task_completed = self._run_single_task(task)
            results.extend(task_results)

            if self._stop_requested:
                return results, False

            if self._paused:
                self._wait_until_resumed_or_stopped()
                if self._stop_requested:
                    return results, False
                # Keep the current attempt and saved step progress after resuming.
                continue

            if task_completed:
                return results, True

            failure_message = self._last_failure_message or f"任务 {task_name} 未完成"
            self._emit(
                f"任务 {task_name} 第 {attempt}/{self.MAX_TASK_ATTEMPTS} 次完整流程失败："
                f"{failure_message}"
            )
            if attempt >= self.MAX_TASK_ATTEMPTS:
                self._emit(
                    f"任务 {task_name} 连续 {self.MAX_TASK_ATTEMPTS} 次未完成，跳过当前任务"
                )
                return results, False

            self._run_before_retry_hook(task, failure_message)
            if self._stop_requested:
                return results, False
            if self._paused:
                self._wait_until_resumed_or_stopped()
                if self._stop_requested:
                    return results, False

            attempt += 1
            self._reset_task_for_retry(task)
            self._emit(f"任务 {task_name} 将从头开始第 {attempt}/{self.MAX_TASK_ATTEMPTS} 次尝试")
            self._emit_task_attempt_start(task_name, attempt)

        return results, False

    def _emit_task_attempt_start(self, task_name: str, attempt: int) -> None:
        self._emit(
            f">>> 开始执行任务 {self.current_task_index + 1}/{self.total_tasks}: {task_name} "
            f"(第 {attempt}/{self.MAX_TASK_ATTEMPTS} 次)"
        )

    def _wait_until_resumed_or_stopped(self) -> None:
        """等待暂停恢复，保留当前任务的步骤和尝试次数。"""
        while self._paused and not self._stop_requested:
            time.sleep(0.1)

    def _run_before_retry_hook(self, task: GameTask, failure_message: str) -> None:
        """Run retry recovery without replacing the task failure that triggered it."""
        try:
            task.before_retry("task", failure_message)
        except Exception as exc:
            task_name = getattr(task, "task_name", task.__class__.__name__)
            self._emit(f"任务 {task_name} 异常重试前恢复失败，仍继续重试：{exc}")

    def _reset_task_for_retry(self, task: GameTask) -> None:
        """将任务恢复为一次完整流程的起点。"""
        self.current_step_index = 0
        self._started_task_index = None
        task._current_step_index = 0
        task._jump_target = None
        task._stop_requested = False
        self._last_failure_message = None
        self._emit_progress()

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

        # 调用任务启动钩子（暂停恢复时不重复调用，完整重试时会重置该标记）。
        if self._started_task_index != self.current_task_index:
            if hasattr(task, "before_start"):
                try:
                    task.before_start()
                except Exception as exc:
                    return self._handle_lifecycle_failure(
                        results,
                        task_name,
                        "before_start",
                        exc,
                    )
            if hasattr(task, "on_start"):
                try:
                    task.on_start()
                except Exception as exc:
                    return self._handle_lifecycle_failure(
                        results,
                        task_name,
                        "on_start",
                        exc,
                    )
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
                    self._emit(f"    {self._last_failure_message}")
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
            try:
                task.on_finish(results)
            except Exception as exc:
                return self._handle_lifecycle_failure(
                    results,
                    task_name,
                    "on_finish",
                    exc,
                )

        return results, not self._paused and not self._stop_requested

    def _handle_lifecycle_failure(
        self,
        results: list[ExecutionResult],
        task_name: str,
        hook_name: str,
        exc: Exception,
    ) -> tuple[list[ExecutionResult], bool]:
        """Convert a task lifecycle hook exception into a retryable task failure."""
        if not self._paused and not self._stop_requested:
            self._last_failure_message = f"任务 {task_name} 生命周期 {hook_name} 执行异常：{exc}"
            self._emit(f"    {self._last_failure_message}")
            self._emit_progress()
        return results, False

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
