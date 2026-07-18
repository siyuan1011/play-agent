"""Executor for Python DSL tasks."""

from __future__ import annotations

import time
from typing import Any, Callable

from .adb_client import ADBClient
from .execution import DslStepExecutor, resolve_step_jump
from .logger import RunLogger
from .models import ExecutionResult
from .task import GameTask
from .vision import VisionEngine


class DSLTaskRunner:
    """Runner for Python DSL tasks."""

    def __init__(
        self,
        task: GameTask,
        adb_client: ADBClient,
        vision: VisionEngine,
        *,
        logger: RunLogger | None = None,
        event_callback: Callable[[str], None] | None = None,
        verbose: bool = False,
    ):
        self.task = task
        self.adb = adb_client
        self.vision = vision
        self.logger = logger
        self.event_callback = event_callback
        self.verbose = verbose
        self._stop_requested = False
        self._executor = DslStepExecutor(
            should_stop=lambda: self._stop_requested,
            emit=self._emit,
        )

    def stop(self) -> None:
        self._stop_requested = True
        self.task.stop()

    def run(self) -> list[ExecutionResult]:
        self._stop_requested = False
        self.adb.ensure_device()

        screen_size = self.adb.get_screen_size()
        self._emit(f"Connected to {self.adb.serial}, resolution={screen_size}")

        test_shot = self.adb.screenshot()
        h, w = test_shot.shape[:2]
        self._emit(f"Screenshot size: {w}x{h}, wm size: {screen_size[0]}x{screen_size[1]}")

        if (w, h) != screen_size:
            self._emit(f"WARNING: Resolution mismatch! Using screenshot size {w}x{h}")
            screen_size = (w, h)

        self.task._screen_resolution = screen_size
        self.task.setup(
            self.adb,
            self.vision,
            self.logger,
            self.event_callback,
            verbose=self.verbose,
        )

        if hasattr(self.task, "before_start"):
            self.task.before_start()

        if hasattr(self.task, "on_start"):
            self.task.on_start()

        results: list[ExecutionResult] = []
        steps = self.task.get_steps()
        loop_count = max(1, self.task.loop_count)

        for round_idx in range(loop_count):
            if self._stop_requested:
                break
            self._emit(f"Loop {round_idx + 1}/{loop_count}")

            step_index = 0
            while step_index < len(steps):
                if self._stop_requested:
                    break

                step_name, step_func, step_meta = steps[step_index]
                self.task._current_step_index = step_index

                if not step_meta.get("enabled", True):
                    step_index += 1
                    continue

                self._emit(f"[{step_name}] 开始")
                result = self._execute_step(step_name, step_func, step_meta)
                results.append(result)

                if self.logger:
                    self.logger.log_step_result(step_name, result)

                self._emit(
                    f"[{step_name}] {'OK' if result.success else 'FAIL'} - "
                    f"{result.reason} ({result.elapsed_ms} ms)"
                )

                if self.task._jump_target:
                    target = self.task._jump_target
                    self.task._jump_target = None

                    jump = resolve_step_jump(target, steps, step_index)
                    if jump.message:
                        self._emit(f"[{step_name}] {jump.message}")
                    if jump.end_loop:
                        break
                    step_index = jump.next_index
                    continue

                step_index += 1

                interval_ms = step_meta.get("interval_ms") or self.task._default_interval_ms
                if interval_ms is not None and interval_ms > 0:
                    time.sleep(interval_ms / 1000.0)

        if hasattr(self.task, "on_finish"):
            self._emit(f">>> {self.task.__class__.__name__} 开始收尾")
            self.task.on_finish(results)
            self._emit(f">>> {self.task.__class__.__name__} 收尾完成")

        return results

    def _execute_step(
        self,
        name: str,
        func: Callable[[GameTask], Any],
        meta: dict,
    ) -> ExecutionResult:
        return self._executor.execute(self.task, name, func, meta)

    def _emit(self, message: str) -> None:
        if self.event_callback:
            self.event_callback(message)
        if self.logger:
            self.logger.log_event({"message": message, "level": "INFO", "source": "runner"})
