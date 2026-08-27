from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from botCore import GameTask, VisionEngine, step
from ymjh_bot import run_queue
from ymjh_bot.run_queue import apply_role_cli_selection, parse_args, resolve_role_indices
from ymjh_bot.runner.account_role_switcher import AccountRoleSwitcher
from ymjh_bot.runner.task_queue_runner import TaskQueueRunner
from ymjh_bot.ui.task_queue_state import load_state, save_state
from ymjh_bot.ym_game_task import LoginState


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ymjh" / "role_selection"
NAV_FIXTURE_DIR = (
    Path(__file__).parent / "fixtures" / "ymjh" / "role_switch_navigation"
)


class FakeADB:
    serial = "test-device"

    def ensure_device(self) -> None:
        pass

    def get_screen_size(self) -> tuple[int, int]:
        return (1280, 720)

    def screenshot(self) -> np.ndarray:
        return np.zeros((720, 1280, 3), dtype=np.uint8)


class StaticScreenshotADB(FakeADB):
    def __init__(self, screenshot: np.ndarray) -> None:
        self._screenshot = screenshot

    def screenshot(self) -> np.ndarray:
        return self._screenshot.copy()

    def tap(self, x: int, y: int) -> None:
        pass


class RecordingTask(GameTask):
    task_name = "记录任务"

    def __init__(self, generation: int, executions: list[int]) -> None:
        super().__init__()
        self.generation = generation
        self.executions = executions

    @step(retry=1, timeout_ms=1000)
    def record(self) -> bool:
        self.executions.append(self.generation)
        return True


class RecordingRoleSwitcher:
    def __init__(self) -> None:
        self._screen_resolution: tuple[int, int] | None = None
        self.roles: list[int] = []
        self.setup_calls = 0
        self.stopped = False

    def setup(self, *args, **kwargs) -> None:
        self.setup_calls += 1

    def switch_to_role(self, role_index: int) -> None:
        self.roles.append(role_index)

    def stop(self) -> None:
        self.stopped = True

    def reset_stop(self) -> None:
        self.stopped = False


def test_arbitrary_role_queue_restarts_the_whole_graph_with_fresh_tasks() -> None:
    executions: list[int] = []
    generations: list[RecordingTask] = []

    def task_factory() -> list[GameTask]:
        task = RecordingTask(len(generations) + 1, executions)
        generations.append(task)
        return [task]

    switcher = RecordingRoleSwitcher()
    runner = TaskQueueRunner(
        task_factory(),
        FakeADB(),  # type: ignore[arg-type]
        VisionEngine(),
        role_indices=[4, 0, 2],
        task_factory=task_factory,
        role_switcher=switcher,
    )

    results = runner.run()

    assert len(results) == 3
    assert executions == [1, 2, 3]
    assert switcher.roles == [0, 2, 4]
    assert switcher.setup_calls == 3
    assert len({id(task) for task in generations}) == 3
    assert runner.get_progress() == {
        "current_role_index": 3,
        "current_task_index": 0,
        "current_step_index": 0,
    }


def test_saved_role_cursor_maps_to_actual_selected_role_before_resuming() -> None:
    executions: list[int] = []
    switcher = RecordingRoleSwitcher()
    runner = TaskQueueRunner(
        [RecordingTask(7, executions)],
        FakeADB(),  # type: ignore[arg-type]
        VisionEngine(),
        role_indices=[0, 2, 4],
        task_factory=lambda: [RecordingTask(8, executions)],
        role_switcher=switcher,
    )
    runner.load_progress(
        {
            "current_role_index": 1,
            "current_task_index": 0,
            "current_step_index": 0,
        }
    )

    runner.run()

    assert switcher.roles == [2, 4]
    assert executions == [7, 8]


def test_single_explicit_role_still_navigates_and_verifies_first() -> None:
    executions: list[int] = []
    events: list[str] = []
    switcher = RecordingRoleSwitcher()
    runner = TaskQueueRunner(
        [RecordingTask(1, executions)],
        FakeADB(),  # type: ignore[arg-type]
        VisionEngine(),
        event_callback=events.append,
        role_indices=[3],
        role_switcher=switcher,
    )

    runner.run()

    assert switcher.roles == [3]
    assert executions == [1]
    assert "本次账号角色队列：4" in events
    assert "本次仅执行角色 4，完成后不会切换到其他角色" in events


def test_role_switch_failure_does_not_execute_tasks_or_advance_cursor() -> None:
    executions: list[int] = []

    class FailingRoleSwitcher(RecordingRoleSwitcher):
        def switch_to_role(self, role_index: int) -> None:
            super().switch_to_role(role_index)
            raise RuntimeError("role verification failed")

    runner = TaskQueueRunner(
        [RecordingTask(1, executions)],
        FakeADB(),  # type: ignore[arg-type]
        VisionEngine(),
        role_indices=[4],
        role_switcher=FailingRoleSwitcher(),
    )

    with pytest.raises(RuntimeError, match="role verification failed"):
        runner.run()

    assert executions == []
    assert runner.get_progress()["current_role_index"] == 0


def test_pause_resume_preserves_selected_role_cursor() -> None:
    switcher = RecordingRoleSwitcher()
    runner = TaskQueueRunner(
        [RecordingTask(1, [])],
        FakeADB(),  # type: ignore[arg-type]
        VisionEngine(),
        role_indices=[0, 2, 4],
        task_factory=lambda: [RecordingTask(2, [])],
        role_switcher=switcher,
    )
    runner.load_progress(
        {
            "current_role_index": 1,
            "current_task_index": 0,
            "current_step_index": 0,
        }
    )

    runner.pause()
    paused_progress = runner.get_progress()
    runner.resume()

    assert paused_progress["current_role_index"] == 1
    assert runner.get_progress() == paused_progress
    assert runner.is_paused() is False
    assert switcher.stopped is False


def test_explicit_role_queue_requires_navigation_and_multi_role_factory() -> None:
    with pytest.raises(ValueError, match="require role_switcher"):
        TaskQueueRunner(
            [RecordingTask(1, [])],
            FakeADB(),  # type: ignore[arg-type]
            VisionEngine(),
            role_indices=[0],
        )

    with pytest.raises(ValueError, match="require task_factory"):
        TaskQueueRunner(
            [RecordingTask(1, [])],
            FakeADB(),  # type: ignore[arg-type]
            VisionEngine(),
            role_indices=[0, 1],
            role_switcher=RecordingRoleSwitcher(),
        )


def _synthetic_role_page(selected_role: int) -> np.ndarray:
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    center_y = AccountRoleSwitcher.ROLE_POINTS[selected_role][1]
    frame[
        center_y - AccountRoleSwitcher.ROLE_SELECTED_STRIP_HALF_HEIGHT :
        center_y + AccountRoleSwitcher.ROLE_SELECTED_STRIP_HALF_HEIGHT,
        AccountRoleSwitcher.ROLE_SELECTED_STRIP_X :
        AccountRoleSwitcher.ROLE_SELECTED_STRIP_X
        + AccountRoleSwitcher.ROLE_SELECTED_STRIP_WIDTH,
    ] = 255
    return frame


class ProbeAccountRoleSwitcher(AccountRoleSwitcher):
    ROLE_SELECT_TIMEOUT_MS = 3
    ROLE_SELECT_POLL_INTERVAL_MS = 1

    def __init__(self, screenshots: list[np.ndarray]) -> None:
        super().__init__()
        self.actions: list[object] = []
        self._screenshots = screenshots
        self._screenshot_index = 0
        self.saved_debug_names: list[str] = []

    def ensure_game_started(self, *, force: bool = False) -> None:
        self.actions.append("ensure")

    def _is_role_page_visible(self) -> bool:
        self.actions.append("role_page_check")
        return True

    def close_all_panels(self, *args, **kwargs) -> None:
        self.actions.append("close")

    def wake_from_power_saving_if_needed(self) -> bool:
        return False

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.actions.append((x, y))

    def wait(self, ms: int | float) -> None:
        self.actions.append(("wait", int(ms)))
        time.sleep(float(ms) / 1000.0)

    def wait_image_appear(self, *args, **kwargs) -> bool:
        self.actions.append("role_page")
        return True

    def screenshot(self) -> np.ndarray:
        index = min(self._screenshot_index, len(self._screenshots) - 1)
        frame = self._screenshots[index]
        self._screenshot_index += 1
        return frame.copy()

    def enter_game(self) -> None:
        self.actions.append("enter")

    def save_debug_screenshot(self, name: str) -> Path:
        self.saved_debug_names.append(name)
        return Path(f"{name}.png")

    def _log(self, message: str) -> None:
        pass

    def _debug(self, message: str) -> None:
        pass


class SettingsNavigationProbe(AccountRoleSwitcher):
    def __init__(self, settings_wait_results: list[bool]) -> None:
        super().__init__()
        self.actions: list[object] = []
        self.settings_wait_results = settings_wait_results
        self.saved_debug_names: list[str] = []

    def _is_settings_page_visible(self) -> bool:
        self.actions.append("settings_check")
        return False

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.actions.append((x, y))

    def _wait_for_settings_page(self, timeout_ms: int) -> bool:
        self.actions.append(("wait_settings", timeout_ms))
        return self.settings_wait_results.pop(0)

    def wait(self, ms: int | float) -> None:
        self.actions.append(("wait", int(ms)))

    def save_debug_screenshot(self, name: str) -> Path:
        self.saved_debug_names.append(name)
        return Path(f"{name}.png")

    def _log(self, message: str) -> None:
        pass


class ConfirmNavigationProbe(AccountRoleSwitcher):
    def __init__(self, *, confirm_found: bool = True, role_page_found: bool = True) -> None:
        super().__init__()
        self.actions: list[object] = []
        self.confirm_found = confirm_found
        self.role_page_found = role_page_found
        self.saved_debug_names: list[str] = []

    def _is_settings_page_visible(self) -> bool:
        self.actions.append("settings_check")
        return True

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.actions.append((x, y))

    def wait_image_appear(self, template, *args, **kwargs) -> bool:
        if template == self.BTN_MODAL_OK:
            self.actions.append("wait_confirm")
            if self.confirm_found:
                self._last_match_center = (854, 508)
            return self.confirm_found
        if template == self.BTN_JRYX:
            self.actions.append("wait_role_page")
            return self.role_page_found
        raise AssertionError(f"unexpected template: {template}")

    def click(self, offset: int = 3) -> None:
        self.actions.append(("click_match", self._last_match_center))

    def wait(self, ms: int | float) -> None:
        self.actions.append(("wait", int(ms)))

    def save_debug_screenshot(self, name: str) -> Path:
        self.saved_debug_names.append(name)
        return Path(f"{name}.png")

    def _log(self, message: str) -> None:
        pass


class DirtyMainRecoveryRoleSwitcher(AccountRoleSwitcher):
    def __init__(self) -> None:
        super().__init__()
        self.state = self.LOGIN_STATE_DIRTY_MAIN
        self.actions: list[object] = []

    def _is_role_page_visible(self) -> bool:
        self.actions.append("role_page_check")
        return False

    def is_game_foreground(self) -> bool:
        return True

    def wake_from_power_saving_if_needed(self) -> bool:
        self.actions.append("wake")
        return False

    def detect_login_state(self, **kwargs):
        self.actions.append(("detect", self.state))
        return LoginState(self.state, self.state, 1.0, (100, 100), "state.png")

    def close_all_panels(self, *args, **kwargs) -> None:
        self.actions.append("close")
        self.state = self.LOGIN_STATE_MAIN

    def _navigate_from_main_to_role_page(self) -> None:
        self.actions.append("navigate")

    def _select_role_and_enter(self, role_index: int) -> None:
        self.actions.append(("select", role_index))

    def _log(self, message: str) -> None:
        pass


def test_account_role_switcher_has_five_fixed_click_coordinates() -> None:
    assert AccountRoleSwitcher.ROLE_POINTS == (
        (1125, 61),
        (1125, 159),
        (1125, 258),
        (1125, 356),
        (1125, 455),
    )
    assert AccountRoleSwitcher.ROLE_SELECT_MAX_ATTEMPTS == 3
    assert AccountRoleSwitcher.ROLE_SELECT_TIMEOUT_MS == 2000
    assert AccountRoleSwitcher.ROLE_SELECT_POLL_INTERVAL_MS == 200


def test_role_switcher_recovers_dirty_main_before_settings_navigation() -> None:
    switcher = DirtyMainRecoveryRoleSwitcher()

    switcher.switch_to_role(2)

    recovery_close = switcher.actions.index("close")
    navigate = switcher.actions.index("navigate")
    select = switcher.actions.index(("select", 2))
    assert recovery_close < navigate < select
    assert ("detect", AccountRoleSwitcher.LOGIN_STATE_DIRTY_MAIN) in switcher.actions
    assert ("detect", AccountRoleSwitcher.LOGIN_STATE_MAIN) in switcher.actions




@pytest.mark.parametrize(
    ("fixture_name", "role_page", "settings_page", "switch_confirm"),
    (
        ("main_menu_collapsed.webp", False, False, False),
        ("system_menu_expanded.webp", False, False, False),
        ("settings_page.webp", False, True, False),
        ("switch_confirm.webp", False, True, True),
        ("role_page_role1.webp", True, False, False),
    ),
)
def test_real_navigation_fixtures_identify_each_switch_stage(
    fixture_name: str,
    role_page: bool,
    settings_page: bool,
    switch_confirm: bool,
) -> None:
    screenshot = cv2.imread(str(NAV_FIXTURE_DIR / fixture_name), cv2.IMREAD_COLOR)
    assert screenshot is not None
    switcher = AccountRoleSwitcher()
    switcher.setup(StaticScreenshotADB(screenshot), VisionEngine())  # type: ignore[arg-type]

    assert switcher._is_role_page_visible() is role_page
    assert switcher._is_settings_page_visible() is settings_page
    assert switcher.find_image(
        switcher.BTN_MODAL_OK,
        threshold=0.85,
        roi=switcher.scale_roi(switcher.ROI_CENTER_MODAL_OK),
    ) is switch_confirm


def test_open_settings_expands_secondary_menu_only_after_direct_attempt_fails() -> None:
    switcher = SettingsNavigationProbe([False, True])

    switcher._open_settings_page()

    assert switcher.actions == [
        "settings_check",
        AccountRoleSwitcher.POINT_SETTINGS,
        ("wait_settings", AccountRoleSwitcher.SETTINGS_PAGE_TIMEOUT_MS),
        AccountRoleSwitcher.POINT_SYSTEM_MENU_MORE,
        ("wait", AccountRoleSwitcher.SETTINGS_OPEN_WAIT_MS),
        AccountRoleSwitcher.POINT_SETTINGS,
        ("wait_settings", AccountRoleSwitcher.SETTINGS_PAGE_TIMEOUT_MS),
    ]


def test_switch_role_confirmation_is_clicked_before_waiting_for_role_page() -> None:
    switcher = ConfirmNavigationProbe()

    switcher._request_role_page_from_settings()

    assert switcher.actions == [
        "settings_check",
        AccountRoleSwitcher.POINT_SWITCH_ROLE,
        "wait_confirm",
        ("click_match", (854, 508)),
        ("wait", AccountRoleSwitcher.SWITCH_CONFIRM_SETTLE_WAIT_MS),
        "wait_role_page",
    ]


def test_missing_switch_confirmation_saves_stage_screenshot_and_stops() -> None:
    switcher = ConfirmNavigationProbe(confirm_found=False)

    with pytest.raises(RuntimeError, match="未出现确认弹窗"):
        switcher._request_role_page_from_settings()

    assert "wait_role_page" not in switcher.actions
    assert switcher.saved_debug_names == ["switch_role_confirm_not_found"]


@pytest.mark.parametrize(
    ("fixture_name", "expected_role"),
    (("selected_role_2.png", 1), ("selected_role_5.png", 4)),
)
def test_real_role_page_fixture_detects_only_selected_white_strip(
    fixture_name: str,
    expected_role: int,
) -> None:
    screenshot = cv2.imread(str(FIXTURE_DIR / fixture_name), cv2.IMREAD_COLOR)
    assert screenshot is not None

    selected_role, scores = AccountRoleSwitcher.detect_selected_role(screenshot)

    assert selected_role == expected_role
    assert scores[expected_role] >= 0.85
    assert all(score < 0.85 for index, score in enumerate(scores) if index != expected_role)


def test_default_selected_target_skips_role_click() -> None:
    switcher = ProbeAccountRoleSwitcher([_synthetic_role_page(1)])

    switcher.switch_to_role(1)

    assert "ensure" not in switcher.actions
    assert AccountRoleSwitcher.ROLE_POINTS[1] not in switcher.actions
    assert switcher.actions[-1] == "enter"


def test_role_click_is_accepted_only_after_white_strip_moves_to_target() -> None:
    switcher = ProbeAccountRoleSwitcher(
        [_synthetic_role_page(0), _synthetic_role_page(2)]
    )

    switcher.switch_to_role(2)

    assert switcher.actions.count(AccountRoleSwitcher.ROLE_POINTS[2]) == 1
    assert switcher.actions[-1] == "enter"


def test_three_failed_role_selection_attempts_never_enter_game() -> None:
    switcher = ProbeAccountRoleSwitcher([_synthetic_role_page(0)])

    with pytest.raises(RuntimeError, match="未检测到右侧纯白选中区域"):
        switcher.switch_to_role(4)

    assert switcher.actions.count(AccountRoleSwitcher.ROLE_POINTS[4]) == 3
    assert "enter" not in switcher.actions
    assert switcher.saved_debug_names == ["role_5_selection_failed"]


def test_legacy_role_count_migrates_and_preserves_role_cursor(tmp_path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "role_count": 8,
                "progress": {
                    "current_role_index": 1,
                    "current_task_index": 3,
                    "current_step_index": 4,
                },
            }
        ),
        encoding="utf-8",
    )

    state = load_state(path)

    assert state["selected_role_indices"] == [0, 1, 2, 3, 4]
    assert state["progress"] == {
        "current_role_index": 1,
        "current_task_index": 3,
        "current_step_index": 4,
    }
    save_state(path, state)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["selected_role_indices"] == [0, 1, 2, 3, 4]
    assert "role_count" not in saved


@pytest.mark.parametrize("selected_roles", ([0, 2, 4], []))
def test_explicit_role_checkbox_selection_round_trips(
    tmp_path,
    selected_roles: list[int],
) -> None:
    path = tmp_path / "state.json"
    save_state(path, {"selected_role_indices": selected_roles})

    assert load_state(path)["selected_role_indices"] == selected_roles


def test_repeatable_role_cli_and_legacy_roles_cli_resolve_expected_queue() -> None:
    state = {"selected_role_indices": [0], "progress": {"current_role_index": 0}}
    repeated = parse_args(
        ["--serial", "test", "--role", "5", "--role", "1", "--role", "3"]
    )
    legacy = parse_args(["--serial", "test", "--roles", "3"])

    assert resolve_role_indices(repeated, state) == ([0, 2, 4], True)
    assert resolve_role_indices(legacy, state) == ([0, 1, 2], True)


def test_changed_cli_role_queue_is_saved_without_stale_progress() -> None:
    state = {
        "selected_role_indices": [0, 1],
        "progress": {
            "current_role_index": 1,
            "current_task_index": 2,
            "current_step_index": 3,
        },
    }
    args = parse_args(["--serial", "test", "--role", "1", "--role", "3"])

    updated, roles, should_save = apply_role_cli_selection(args, state)

    assert roles == [0, 2]
    assert updated["selected_role_indices"] == [0, 2]
    assert "progress" not in updated
    assert should_save is True


def test_headless_start_rejects_saved_empty_role_selection(tmp_path, monkeypatch) -> None:
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(
        run_queue,
        "load_state_for_serial",
        lambda *args, **kwargs: (
            {"selected_role_indices": [], "selected_task_keys": []},
            state_path,
        ),
    )

    assert run_queue.main(["--serial", "test-device"]) == 2
