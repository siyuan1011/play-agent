from __future__ import annotations

import pytest

from ymjh_bot.ym_game_task import LoginState, YmGameTask


class ForegroundStartupTask(YmGameTask):
    DEFER_FOREGROUND_WAKE_TO_ON_START = True

    def __init__(self, state: str) -> None:
        super().__init__()
        self.state = state
        self.detect_calls = 0
        self.enter_game_calls = 0
        self.launch_calls = 0
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
