"""
Python DSL for defining game automation tasks.

Usage:
    from botCore import GameTask, step

    class MyTask(GameTask):
        design_resolution = (1280, 720)

        @step(retry=3)
        def close_popup(self):
            if self.find_image("btn_close.png"):
                self.click()
                return True
            return False
"""

from __future__ import annotations

import time
from typing import Any, Callable, Protocol, runtime_checkable

import numpy as np

from .adb_client import ADBClient
from .coords import apply_random_offset, scale_point
from .logger import RunLogger
from .vision import VisionEngine


class StepJumpException(Exception):
    """Raised to jump to another DSL step."""

    JUMP_TO_START = "__start__"
    JUMP_TO_END = "__end__"
    JUMP_TO_PREV = "__prev__"
    JUMP_TO_NEXT = "__next__"

    def __init__(self, target: str):
        self.target = target
        super().__init__(f"Jump to: {target}")


@runtime_checkable
class StepCallable(Protocol):
    def __call__(self, __self: "GameTask") -> Any: ...


def step(
    retry: int | None = 3,
    timeout_ms: int | None = 30000,
    enabled: bool = True,
    interval_ms: int | None = None,
):
    """Decorator to mark a method as a task step."""

    def decorator(func: Callable[["GameTask"], Any]) -> StepCallable:
        func._step_meta = {
            "retry": retry,
            "timeout_ms": timeout_ms,
            "enabled": enabled,
            "interval_ms": interval_ms,
        }
        return func

    return decorator


class StepStopException(Exception):
    """Raised when stop is requested during a blocking operation."""


class GameTask:
    """Base class for game automation tasks using Python DSL."""

    design_resolution: tuple[int, int] = (1280, 720)
    loop_count: int = 1

    _adb: ADBClient
    _vision: VisionEngine
    _logger: RunLogger | None
    _event_callback: Callable[[str], None] | None
    _stop_requested: bool
    _verbose: bool
    _screen_resolution: tuple[int, int] | None
    _jump_target: str | None
    _current_step_index: int

    def __init__(self, default_interval_ms: int | None = None):
        self._stop_requested = False
        self._screen_resolution = None
        self._last_match_center: tuple[int, int] | None = None
        self._last_match_score: float = 0.0
        self._default_interval_ms = default_interval_ms
        self._logger: RunLogger | None = None
        self._event_callback: Callable[[str], None] | None = None
        self._verbose = False
        self._jump_target: str | None = None
        self._current_step_index = 0

    def setup(
        self,
        adb: ADBClient,
        vision: VisionEngine,
        logger: RunLogger | None = None,
        event_callback: Callable[[str], None] | None = None,
        verbose: bool = False,
    ) -> None:
        self._adb = adb
        self._vision = vision
        self._logger = logger
        self._event_callback = event_callback
        self._verbose = verbose

    @classmethod
    def get_steps(cls) -> list[tuple[str, Callable[["GameTask"], Any], dict]]:
        """Get all step methods with their metadata in definition order."""
        import inspect

        steps = []
        try:
            source = inspect.getsource(cls)
            lines = source.split("\n")
            step_methods = {}
            for lineno, line in enumerate(lines):
                if "@step" in line and lineno + 1 < len(lines) and "def " in lines[lineno + 1]:
                    method_name = lines[lineno + 1].split("def ")[1].split("(")[0]
                    step_methods[method_name] = lineno
            for name in sorted(step_methods.keys(), key=lambda x: step_methods[x]):
                attr = getattr(cls, name)
                if callable(attr) and hasattr(attr, "_step_meta"):
                    steps.append((name, attr, attr._step_meta))
            return steps
        except Exception:
            pass

        step_methods = []
        for name, attr in cls.__dict__.items():
            if callable(attr) and hasattr(attr, "_step_meta"):
                step_methods.append((name, attr, attr._step_meta))
        if step_methods:
            return step_methods

        for name in dir(cls):
            attr = getattr(cls, name)
            if callable(attr) and hasattr(attr, "_step_meta"):
                steps.append((name, attr, attr._step_meta))
        return steps

    def stop(self) -> None:
        self._stop_requested = True

    def reset_stop(self) -> None:
        """Clear a propagated stop flag before resume or a fresh retry."""
        self._stop_requested = False

    def is_stopped(self) -> bool:
        return self._stop_requested

    def before_step(self, step_name: str, step_meta: dict[str, Any]) -> None:
        """Hook called immediately before each DSL step attempt."""

    def before_retry(
        self,
        retry_scope: str,
        failure: Exception | str | None = None,
    ) -> None:
        """Hook called after an abnormal failure and before an actual retry."""

    def cleanup_after_failure(
        self,
        failure: Exception | str | None = None,
    ) -> None:
        """Clean task-owned external state after a failed full task attempt."""

    def recover_after_cleanup_failure(
        self,
        failure: Exception | str | None = None,
    ) -> None:
        """Recover external state when normal task cleanup cannot prove safety."""
        raise RuntimeError(
            f"任务 {self.__class__.__name__} 不支持失败清理后的强制恢复"
        )

    def jump_to(self, step_name: str) -> None:
        raise StepJumpException(step_name)

    def jump_to_start(self) -> None:
        raise StepJumpException(StepJumpException.JUMP_TO_START)

    def jump_to_end(self) -> None:
        raise StepJumpException(StepJumpException.JUMP_TO_END)

    def jump_to_prev(self) -> None:
        raise StepJumpException(StepJumpException.JUMP_TO_PREV)

    def jump_to_next(self) -> None:
        raise StepJumpException(StepJumpException.JUMP_TO_NEXT)

    def get_current_step_name(self) -> str | None:
        steps = self.get_steps()
        if 0 <= self._current_step_index < len(steps):
            return steps[self._current_step_index][0]
        return None

    def tap(self, x: int | None = None, y: int | None = None) -> None:
        if x is None or y is None:
            if self._last_match_center:
                x, y = self._last_match_center
            else:
                raise RuntimeError("No position to tap. Provide coordinates or find_image first.")
        self._adb.tap(x, y)
        self._debug(f"Clicked at ({x}, {y})")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 400) -> None:
        self._adb.swipe(x1, y1, x2, y2, duration_ms)
        self._debug(f"Swiped ({x1},{y1}) -> ({x2},{y2})")

    def shell(self, command: str) -> str:
        return self._adb.shell(command)

    def screenshot(self) -> np.ndarray:
        return self._adb.screenshot()

    def find_image(
        self,
        template: str | list[str],
        threshold: float = 0.8,
        roi: tuple[int, int, int, int] | None = None,
    ) -> bool:
        templates = [template] if isinstance(template, str) else template
        screenshot = self.screenshot()
        match = self._vision.match_template(screenshot, templates, threshold=threshold, roi=roi)
        self._last_match_score = match.score
        if match.found and match.center:
            self._last_match_center = match.center
            self._debug(f"Found image: {template} (score={match.score:.3f})")
            return True
        self._last_match_center = None
        self._debug(f"Image not found: {template} (score={match.score:.3f})")
        return False

    def wait_image_appear(
        self,
        template: str | list[str],
        timeout_ms: int | None = 10000,
        threshold: float = 0.8,
        callback: Callable[[bool], None] | None = None,
        interval_ms: int = 500,
        roi: tuple[int, int, int, int] | None = None,
    ) -> bool:
        start = time.perf_counter()
        deadline = None if timeout_ms is None else start + timeout_ms / 1000.0

        while deadline is None or time.perf_counter() < deadline:
            if self._stop_requested:
                raise StepStopException("Stop requested")
            if self.find_image(template, threshold=threshold, roi=roi):
                if callback:
                    callback(True)
                return True
            if callback:
                callback(False)
            remaining_ms = interval_ms if deadline is None else max(
                0, min(interval_ms, int((deadline - time.perf_counter()) * 1000))
            )
            if remaining_ms:
                self.wait(remaining_ms)

        self._last_match_center = None
        self._debug(f"Image not found: {template} (timeout)")
        if callback:
            callback(False)
        return False

    def wait_image_missing(
        self,
        template: str | list[str],
        timeout_ms: int | None = 10000,
        threshold: float = 0.8,
        missing_threshold: int = 3,
        callback: Callable[[bool, int], None] | None = None,
        interval_ms: int = 500,
    ) -> bool:
        start = time.perf_counter()
        deadline = None if timeout_ms is None else start + timeout_ms / 1000.0
        consecutive_missing = 0

        while deadline is None or time.perf_counter() < deadline:
            if self._stop_requested:
                raise StepStopException("Stop requested")
            found = self.find_image(template, threshold)
            if not found:
                consecutive_missing += 1
                if callback:
                    callback(False, consecutive_missing)
                if consecutive_missing >= missing_threshold:
                    return True
            else:
                consecutive_missing = 0
                if callback:
                    callback(True, consecutive_missing)
            remaining_ms = interval_ms if deadline is None else max(
                0, min(interval_ms, int((deadline - time.perf_counter()) * 1000))
            )
            if remaining_ms:
                self.wait(remaining_ms)

        if callback:
            callback(False, consecutive_missing)
        return consecutive_missing >= missing_threshold

    def click(self, offset: int = 3) -> None:
        if self._last_match_center:
            x, y = apply_random_offset(self._last_match_center, offset)
            self.tap(x, y)

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        scaled = scale_point((x, y), self.design_resolution, self._screen_resolution or self.design_resolution)
        if offset > 0:
            x, y = apply_random_offset(scaled, offset)
        else:
            x, y = scaled
        self.tap(x, y)

    def wait(self, ms: int | float) -> None:
        remaining_ms = int(ms)
        while remaining_ms > 0:
            if self._stop_requested:
                raise StepStopException("Stop requested")
            sleep_time = min(remaining_ms, 50)
            time.sleep(sleep_time / 1000.0)
            remaining_ms -= sleep_time

    def _log(self, message: str) -> None:
        self._emit_log(message, level="INFO")

    def _debug(self, message: str) -> None:
        if self._verbose:
            self._emit_log(message, level="DEBUG")

    def _emit_log(self, message: str, *, level: str) -> None:
        if self._event_callback:
            self._event_callback(f"[{self.__class__.__name__}] {message}")
        if self._logger:
            self._logger.log_event({"message": message, "level": level})
        if not self._event_callback and not self._logger:
            print(f"[{self.__class__.__name__}] {message}")
