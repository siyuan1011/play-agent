from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from botCore import VisionEngine, load_image
from ymjh_bot.ym_game_task import LoginState, YmGameTask


FIXTURES = Path(__file__).parent / "fixtures" / "ymjh"


class ForegroundStartupTask(YmGameTask):
    DEFER_FOREGROUND_WAKE_TO_ON_START = True

    def __init__(self, state: str) -> None:
        super().__init__()
        self.state = state
        self.detect_calls = 0
        self.enter_game_calls = 0
        self.launch_calls = 0
        self.cleanup_calls = 0
        self.logs: list[str] = []

    def is_game_foreground(self) -> bool:
        return True

    def is_power_saving_mode(self) -> bool:
        return self.state == "power_saving"

    def detect_login_state(
        self,
        *,
        include_modal_controls: bool = False,
        threshold: float = 0.8,
    ) -> LoginState | None:
        self.detect_calls += 1
        if self.state == "unknown":
            return None
        return LoginState(
            name=self.state,
            description=self.state,
            score=1.0,
            center=(100, 100),
            template_path=f"{self.state}.png",
        )

    def enter_game(self) -> None:
        self.enter_game_calls += 1

    def start_game_app(self, wait_after_launch_ms: int = 5000) -> None:
        self.launch_calls += 1

    def close_all_panels(self, *args, **kwargs) -> None:
        self.cleanup_calls += 1
        if self.state in {"unknown", self.LOGIN_STATE_DIRTY_MAIN}:
            self.state = self.LOGIN_STATE_MAIN

    def _log(self, message: str) -> None:
        self.logs.append(message)


@pytest.mark.parametrize(
    "state",
    [
        YmGameTask.LOGIN_STATE_NOTICE,
        YmGameTask.LOGIN_STATE_LOGIN,
        YmGameTask.LOGIN_STATE_ROLE_CONFIRM,
        YmGameTask.LOGIN_STATE_ROLE,
        YmGameTask.LOGIN_STATE_POPUP,
        YmGameTask.LOGIN_STATE_LOADING,
    ],
)
def test_foreground_non_main_state_enters_login_flow(state: str) -> None:
    task = ForegroundStartupTask(state)

    task.before_start()

    assert task.detect_calls == 1
    assert task.enter_game_calls == 1
    assert task.launch_calls == 0
    assert "检测到游戏在前台但未进入主界面，继续进入游戏" in task.logs


def test_foreground_main_scene_skips_login_flow() -> None:
    task = ForegroundStartupTask(YmGameTask.LOGIN_STATE_MAIN)

    task.before_start()

    assert task.detect_calls == 1
    assert task.enter_game_calls == 0
    assert task.launch_calls == 0
    assert "检测到游戏已在前台，跳过启动" in task.logs


def test_foreground_power_saving_still_defers_wake_to_on_start() -> None:
    task = ForegroundStartupTask("power_saving")

    task.before_start()

    assert task.detect_calls == 0
    assert task.enter_game_calls == 0
    assert task.launch_calls == 0
    assert task.logs == ["检测到游戏已在前台，省电唤醒交给 on_start"]


@pytest.mark.parametrize("state", ["unknown", YmGameTask.LOGIN_STATE_DIRTY_MAIN])
def test_foreground_dirty_scene_is_cleaned_before_login_flow(state: str) -> None:
    task = ForegroundStartupTask(state)

    task.before_start()

    assert task.cleanup_calls == 1
    assert task.detect_calls == 2
    assert task.enter_game_calls == 0
    assert task.state == YmGameTask.LOGIN_STATE_MAIN
    assert "前台界面清理完成，跳过登录流程" in task.logs


class LoginLoopTask(YmGameTask):
    def __init__(self, states: list[str | None]) -> None:
        super().__init__()
        self.states = states
        self.state_index = 0
        self.cleanup_calls = 0
        self.wake_calls = 0
        self.logs: list[str] = []
        self.saved_prefixes: list[str] = []

    def detect_login_state(
        self,
        *,
        include_modal_controls: bool = False,
        threshold: float = 0.8,
    ) -> LoginState | None:
        index = min(self.state_index, len(self.states) - 1)
        self.state_index += 1
        state = self.states[index]
        if state is None:
            return None
        return LoginState(state, state, 1.0, (100, 100), f"{state}.png")

    def wake_from_power_saving_if_needed(self) -> bool:
        self.wake_calls += 1
        return False

    def close_all_panels(self, *args, **kwargs) -> None:
        self.cleanup_calls += 1

    def close_startup_panels(self, **kwargs) -> bool:
        return True

    def wait(self, ms: int | float) -> None:
        return None

    def save_debug_screenshot(self, prefix: str = "debug") -> str:
        self.saved_prefixes.append(prefix)
        return f"{prefix}.png"

    def _log(self, message: str) -> None:
        self.logs.append(message)


def test_enter_game_real_loading_state_waits_without_cleanup() -> None:
    task = LoginLoopTask(
        [YmGameTask.LOGIN_STATE_LOADING, YmGameTask.LOGIN_STATE_MAIN]
    )

    task.enter_game()

    assert task.cleanup_calls == 0
    assert task.wake_calls == 0
    assert task.logs.count("等待登录流程加载...") == 1


def test_enter_game_unknown_scene_runs_wake_and_cleanup() -> None:
    task = LoginLoopTask([None, YmGameTask.LOGIN_STATE_MAIN])

    task.enter_game()

    assert task.wake_calls == 1
    assert task.cleanup_calls == 1
    assert "前台画面未识别，尝试省电唤醒和弹框清理" in task.logs


def test_enter_game_unknown_timeout_saves_debug_screenshot() -> None:
    task = LoginLoopTask([None])
    task.LOGIN_LOADING_TIMEOUT_MS = -1

    with pytest.raises(RuntimeError, match="login_unknown_scene_timeout.png"):
        task.enter_game()

    assert task.saved_prefixes == ["login_unknown_scene_timeout"]


class ForceRecoveryTask(YmGameTask):
    def __init__(self, *, main_ready: bool = True) -> None:
        super().__init__()
        self.main_ready = main_ready
        self.events: list[object] = []

    def shell(self, command: str) -> str:
        self.events.append(("shell", command))
        return ""

    def wait(self, ms: int | float) -> None:
        self.events.append(("wait", ms))

    def start_game_app(self, wait_after_launch_ms: int = 5000) -> None:
        self.events.append("start")

    def enter_game(self) -> None:
        self.events.append("login")

    def close_all_panels(self, *args, **kwargs) -> None:
        self.events.append(("close", kwargs))

    def leave_team(self, *args, **kwargs) -> None:
        self.events.append(("leave", kwargs))

    def is_game_main_ready(self, **kwargs) -> bool:
        self.events.append(("verify", kwargs))
        return self.main_ready

    def save_debug_screenshot(self, prefix: str = "debug") -> str:
        self.events.append(("screenshot", prefix))
        return f"{prefix}.png"

    def _log(self, message: str) -> None:
        return None


def test_cleanup_failure_recovery_restarts_and_verifies_unteamed_main() -> None:
    task = ForceRecoveryTask()

    task.recover_after_cleanup_failure("cleanup failed")

    assert task.events == [
        ("shell", f"am force-stop {task.PACKAGE_NAME}"),
        ("wait", task.FAILURE_RECOVERY_FORCE_STOP_WAIT_MS),
        "start",
        "login",
        ("close", {"timeout_ms": task.STARTUP_FINAL_CLOSE_TIMEOUT_MS}),
        ("leave", {"timeout_ms": 5000, "wait_after_click_ms": 1000}),
        ("close", {"timeout_ms": task.STARTUP_FINAL_CLOSE_TIMEOUT_MS}),
        (
            "verify",
            {
                "timeout_ms": task.FAILURE_RECOVERY_MAIN_VERIFY_TIMEOUT_MS,
                "threshold": 0.8,
            },
        ),
    ]


def test_cleanup_failure_recovery_rejects_unknown_post_restart_scene() -> None:
    task = ForceRecoveryTask(main_ready=False)

    with pytest.raises(RuntimeError, match="cleanup_force_recovery_failed.png"):
        task.recover_after_cleanup_failure("cleanup failed")

    assert task.events[-1] == ("screenshot", "cleanup_force_recovery_failed")


class StaticScreenshotTask(YmGameTask):
    def __init__(self, screenshot: np.ndarray) -> None:
        super().__init__()
        self.frame = screenshot
        self._vision = VisionEngine()

    def screenshot(self) -> np.ndarray:
        return self.frame


def test_detect_login_state_distinguishes_real_loading_from_dirty_calendar() -> None:
    loading_task = StaticScreenshotTask(load_image(FIXTURES / "scene_loading_02.webp"))
    calendar_task = StaticScreenshotTask(
        load_image(
            FIXTURES
            / "login_startup"
            / "dirty_main_calendar_detail_power_saving.webp"
        )
    )

    loading_state = loading_task.detect_login_state(include_modal_controls=True)
    calendar_state = calendar_task.detect_login_state(include_modal_controls=True)

    assert loading_state is not None
    assert loading_state.name == YmGameTask.LOGIN_STATE_LOADING
    assert calendar_state is not None
    assert calendar_state.name == YmGameTask.LOGIN_STATE_DIRTY_MAIN
