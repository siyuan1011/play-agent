from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .models import ExecutionResult
from .task import GameTask, StepJumpException, StepStopException


StepRecord = tuple[str, Callable[[GameTask], Any], dict[str, Any]]


@dataclass(slots=True)
class JumpResolution:
    next_index: int
    end_loop: bool = False
    message: str | None = None


class DslStepExecutor:
    """Shared retry/timeout executor for Python DSL task steps."""

    def __init__(
        self,
        *,
        should_stop: Callable[[], bool],
        emit: Callable[[str], None],
    ) -> None:
        self._should_stop = should_stop
        self._emit = emit

    def execute(
        self,
        task: GameTask,
        name: str,
        func: Callable[[GameTask], Any],
        meta: dict[str, Any],
    ) -> ExecutionResult:
        start = time.perf_counter()
        retry_raw = meta.get("retry", 0)
        attempts = -1 if retry_raw is None or retry_raw == -1 else max(1, int(retry_raw) + 1)

        timeout_raw = meta.get("timeout_ms", 10000)
        deadline = None if timeout_raw is None else start + int(timeout_raw) / 1000.0
        last_error: Exception | None = None

        while attempts == -1 or attempts > 0:
            if self._should_stop():
                return self._result(start, False, "Stopped by user")

            if deadline is not None and time.perf_counter() > deadline:
                break

            try:
                task.before_step(name, meta)
                result_value = func(task)
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                if result_value is None:
                    return ExecutionResult(True, elapsed_ms, "Completed")
                if isinstance(result_value, bool):
                    if result_value:
                        return ExecutionResult(True, elapsed_ms, "Completed")
                    last_error = Exception("Step returned False")
                else:
                    return ExecutionResult(True, elapsed_ms, f"Completed with result: {result_value}")
            except StepJumpException as exc:
                task._jump_target = exc.target
                return self._result(start, True, f"Jump to {exc.target}")
            except StepStopException:
                return self._result(start, False, "Stopped by user")
            except Exception as exc:
                last_error = exc
                self._emit(f"[{name}] Error: {exc}")

            if attempts > 0:
                attempts -= 1

            retry_available = attempts == -1 or attempts > 0
            retry_in_time = deadline is None or time.perf_counter() <= deadline
            if not retry_available or not retry_in_time or self._should_stop():
                break

            hook_started_at = time.perf_counter()
            try:
                task.before_retry("step", last_error)
            except Exception as exc:
                self._emit(f"[{name}] Retry recovery error: {exc}")
            finally:
                if deadline is not None:
                    deadline += time.perf_counter() - hook_started_at

            if self._should_stop():
                return self._result(start, False, "Stopped by user")
            time.sleep(0.15)

        reason = str(last_error) if last_error else "Timeout exceeded"
        return self._result(start, False, reason)

    @staticmethod
    def _result(start: float, success: bool, reason: str) -> ExecutionResult:
        return ExecutionResult(
            success=success,
            elapsed_ms=int((time.perf_counter() - start) * 1000),
            reason=reason,
        )


def resolve_step_jump(
    target: str,
    steps: list[StepRecord],
    current_index: int,
) -> JumpResolution:
    if target == StepJumpException.JUMP_TO_END:
        return JumpResolution(current_index, end_loop=True, message="Jump to end of loop")
    if target == StepJumpException.JUMP_TO_START:
        return JumpResolution(0, message="Jump to start")
    if target == StepJumpException.JUMP_TO_PREV:
        return JumpResolution(max(0, current_index - 1), message="Jump to previous step")
    if target == StepJumpException.JUMP_TO_NEXT:
        return JumpResolution(current_index + 1, message="Jump to next step")

    for idx, (name, _, _) in enumerate(steps):
        if name == target:
            return JumpResolution(idx, message=f"Jump to '{target}'")

    return JumpResolution(
        current_index + 1,
        message=f"WARN: Jump target '{target}' not found",
    )
