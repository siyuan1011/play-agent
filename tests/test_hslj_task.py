from pathlib import Path

import pytest

from botCore import load_task_class
from ymjh_bot.task.HSLJ_task import HSLJTask
from ymjh_bot.ui.task_queue_window import is_visible_task_class


class FakeHsljTask(HSLJTask):
    def __init__(
        self,
        *,
        roi_results: list[bool] | None = None,
        image_results: list[bool] | None = None,
        find_once_results: list[bool] | None = None,
        power_saving_results: list[bool] | None = None,
        safe_zone_error: Exception | None = None,
    ):
        super().__init__()
        self.roi_results = roi_results or []
        self.image_results = image_results or []
        self.find_once_results = find_once_results or []
        self.power_saving_results = power_saving_results or []
        self.roi_calls = []
        self.image_calls = []
        self.find_once_calls = []
        self.open_activity_calls = []
        self.safe_close_panel_calls = []
        self.clicked_points = []
        self.click_offsets = []
        self.swipe_calls = []
        self.wait_calls = []
        self.debug_prefixes = []
        self.safe_zone_calls = []
        self.safe_zone_error = safe_zone_error
        self.logs = []

    def wait_find_image_in_roi(
        self,
        template,
        roi,
        *,
        timeout_ms,
        description,
        threshold=0.8,
        interval_ms=500,
    ):
        self.roi_calls.append((template, roi, timeout_ms, description, threshold, interval_ms))
        return self.roi_results.pop(0) if self.roi_results else False

    def wait_image_appear(self, template, timeout_ms=10000, threshold=0.8, callback=None, interval_ms=500):
        self.image_calls.append((template, timeout_ms, threshold))
        return self.image_results.pop(0) if self.image_results else False

    def find_image_once(self, template, *, threshold=0.8, roi=None, log_found=False, log_missing=False):
        self.find_once_calls.append((template, threshold, roi, log_found, log_missing))
        return self.find_once_results.pop(0) if self.find_once_results else False

    def open_activity_panel(
        self,
        category=None,
        category_name=None,
        *,
        timeout_ms=30000,
        wait_after_open_ms=2000,
        wait_after_category_ms=0,
    ) -> None:
        self.open_activity_calls.append(
            (
                category,
                category_name,
                timeout_ms,
                wait_after_open_ms,
                wait_after_category_ms,
            )
        )

    def close_all_panels_for_hslj(
        self,
        *,
        timeout_ms: int = 5000,
        wait_after_click_ms: int = 500,
        max_attempts: int | None = None,
    ) -> None:
        self.safe_close_panel_calls.append((timeout_ms, wait_after_click_ms, max_attempts))

    def is_power_saving_mode(self) -> bool:
        if self.power_saving_results:
            return self.power_saving_results.pop(0)
        return False

    def click(self, offset: int = 3) -> None:
        self.click_offsets.append(offset)

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.clicked_points.append((x, y, offset))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 400) -> None:
        self.swipe_calls.append((x1, y1, x2, y2, duration_ms))

    def wait(self, ms):
        self.wait_calls.append(ms)

    def return_to_safe_zone(self) -> None:
        self.safe_zone_calls.append(())
        if self.safe_zone_error:
            raise self.safe_zone_error

    def save_debug_screenshot(self, prefix: str) -> str:
        self.debug_prefixes.append(prefix)
        return f"screenshots/{prefix}.png"

    def _log(self, message: str) -> None:
        self.logs.append(message)


class SafeCloseHsljTask(HSLJTask):
    def __init__(self, *, image_results: list[bool] | None = None):
        super().__init__()
        self.image_results = image_results or []
        self.chat_collapse_calls = []
        self.image_calls = []
        self.click_offsets = []
        self.wait_calls = []
        self.logs = []

    def collapse_chat_if_open(self, wait_after_click_ms: int = 800) -> bool:
        self.chat_collapse_calls.append(wait_after_click_ms)
        return False

    def close_purchase_dialog_if_needed(self) -> bool:
        return False

    def wait_image_appear(self, template, timeout_ms=10000, threshold=0.8, callback=None, interval_ms=500):
        self.image_calls.append((template, timeout_ms, threshold))
        return self.image_results.pop(0) if self.image_results else False

    def click(self, offset: int = 3) -> None:
        self.click_offsets.append(offset)

    def wait(self, ms):
        self.wait_calls.append(ms)

    def _log(self, message: str) -> None:
        self.logs.append(message)


class OneVOneFlowTask(HSLJTask):
    def __init__(
        self,
        *,
        complete: bool | None = None,
        claim_results: list[bool] | None = None,
        hslj_settings: dict | None = None,
        stop_after_matches: int | None = None,
    ):
        super().__init__(hslj_settings=hslj_settings)
        if claim_results is None and complete is not None:
            claim_results = [complete]
        self.claim_results = claim_results or []
        self.stop_after_matches = stop_after_matches
        self.ready_calls = []
        self.selected_modes = []
        self.match_clicks = 0
        self.battle_calls = []
        self.claim_calls = []
        self.logs = []

    def ensure_hslj_panel_ready(self, *, mode: str, timeout_ms: int) -> None:
        self.ready_calls.append((mode, timeout_ms))

    def select_hslj_mode(self, mode: str) -> None:
        self.selected_modes.append(mode)

    def claim_first_win_reward(self, mode: str) -> bool:
        self.claim_calls.append(mode)
        return self.claim_results.pop(0) if self.claim_results else False

    def click_match_button(self) -> None:
        self.match_clicks += 1

    def run_match_battle(self, mode: str, match_index: int) -> None:
        self.battle_calls.append((mode, match_index))
        if self.stop_after_matches and match_index >= self.stop_after_matches:
            self.stop()

    def _log(self, message: str) -> None:
        self.logs.append(message)


class ThreeVThreeLoopTask(HSLJTask):
    def __init__(
        self,
        *,
        lunjian_count: int = HSLJTask.DEFAULT_LUNJIAN_COUNT,
        lunjian_infinite: bool = False,
        hslj_settings: dict | None = None,
        claim_results: list[bool] | None = None,
        stop_after_matches: int | None = None,
    ):
        super().__init__(
            lunjian_count=lunjian_count,
            lunjian_infinite=lunjian_infinite,
            hslj_settings=hslj_settings,
        )
        self.claim_results = claim_results or []
        self.stop_after_matches = stop_after_matches
        self.ready_calls = []
        self.selected_modes = []
        self.match_clicks = 0
        self.battle_calls = []
        self.claim_calls = []
        self.logs = []

    def ensure_hslj_panel_ready(self, *, mode: str, timeout_ms: int) -> None:
        self.ready_calls.append((mode, timeout_ms))

    def select_hslj_mode(self, mode: str) -> None:
        self.selected_modes.append(mode)

    def claim_first_win_reward(self, mode: str) -> bool:
        self.claim_calls.append(mode)
        return self.claim_results.pop(0) if self.claim_results else False

    def click_match_button(self) -> None:
        self.match_clicks += 1

    def run_match_battle(self, mode: str, match_index: int) -> None:
        self.battle_calls.append((mode, match_index))
        if self.stop_after_matches and match_index >= self.stop_after_matches:
            self.stop()

    def _log(self, message: str) -> None:
        self.logs.append(message)


class ClaimFirstWinHsljTask(HSLJTask):
    def __init__(
        self,
        *,
        reward_state: str = "unknown",
        panel_visible: bool = True,
        mode_selected: bool = True,
        ready_visible: bool = False,
        result_visible: bool = False,
        match_success_visible: bool = False,
        verify_claimed: bool = True,
    ):
        super().__init__()
        self.reward_state = reward_state
        self.panel_visible = panel_visible
        self.mode_selected = mode_selected
        self.ready_visible = ready_visible
        self.result_visible = result_visible
        self.match_success_visible = match_success_visible
        self.verify_claimed = verify_claimed
        self.click_offsets = []
        self.clicked_points = []
        self.wait_calls = []
        self.close_reward_calls = []
        self.roi_calls = []
        self.logs = []

    def is_ready_button_visible(self) -> bool:
        return self.ready_visible

    def is_result_panel_visible_quiet(self) -> bool:
        return self.result_visible

    def is_match_success_visible_quiet(self) -> bool:
        return self.match_success_visible

    def is_hslj_panel_visible_quiet(self) -> bool:
        return self.panel_visible

    def is_hslj_mode_selected_quiet(self, mode: str) -> bool:
        return self.mode_selected

    def is_first_win_reward_claimed(self) -> bool:
        self._last_match_score = 1.0 if self.reward_state == "claimed" else 0.2
        return self.reward_state == "claimed"

    def is_first_win_reward_ready(self) -> bool:
        self._last_match_score = 1.0 if self.reward_state == "ready" else 0.2
        return self.reward_state == "ready"

    def is_first_win_reward_initial(self) -> bool:
        self._last_match_score = 1.0 if self.reward_state == "initial" else 0.2
        return self.reward_state == "initial"

    def wait_find_image_in_roi(
        self,
        template,
        roi,
        *,
        timeout_ms,
        description,
        threshold=0.8,
        interval_ms=500,
    ):
        self.roi_calls.append((template, roi, timeout_ms, description, threshold, interval_ms))
        return self.verify_claimed

    def close_reward_dialogs(self, max_attempts: int = 4, *, include_close_buttons: bool = True) -> bool:
        self.close_reward_calls.append((max_attempts, include_close_buttons))
        return True

    def click(self, offset: int = 3) -> None:
        self.click_offsets.append(offset)

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.clicked_points.append((x, y, offset))

    def wait(self, ms):
        self.wait_calls.append(ms)

    def _log(self, message: str) -> None:
        self.logs.append(message)


class ModeSwitchHsljTask(HSLJTask):
    def __init__(self, *, selected_results: list[bool]):
        super().__init__()
        self.selected_results = selected_results
        self.clicked_points = []
        self.wait_calls = []
        self.debug_prefixes = []
        self.logs = []

    def ensure_hslj_mode_selected(self, mode: str, *, timeout_ms: int) -> bool:
        return self.selected_results.pop(0) if self.selected_results else False

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.clicked_points.append((x, y, offset))

    def wait(self, ms):
        self.wait_calls.append(ms)

    def save_debug_screenshot(self, prefix: str) -> str:
        self.debug_prefixes.append(prefix)
        return f"screenshots/{prefix}.png"

    def _log(self, message: str) -> None:
        self.logs.append(message)


class ResidualSwitchHsljTask(HSLJTask):
    def __init__(self):
        super().__init__()
        self.ready_calls = []
        self.cancel_calls = []
        self.selected_modes = []
        self.logs = []

    def ensure_hslj_panel_ready(self, *, mode: str, timeout_ms: int) -> None:
        self.ready_calls.append((mode, timeout_ms))

    def resolve_hslj_transient_state(self, mode: str) -> bool:
        return False

    def is_hslj_panel_visible_quiet(self) -> bool:
        return True

    def is_hslj_mode_selected_quiet(self, mode: str) -> bool:
        return False

    def is_match_cancel_button_visible_quiet(self) -> bool:
        return True

    def cancel_current_match(self, mode: str, match_index: int) -> bool:
        self.cancel_calls.append((mode, match_index))
        return True

    def select_hslj_mode(self, mode: str) -> None:
        self.selected_modes.append(mode)

    def _log(self, message: str) -> None:
        self.logs.append(message)


class BattleFlowHsljTask(FakeHsljTask):
    def __init__(
        self,
        *,
        result_visible_results: list[bool],
        panel_visible_results: list[bool] | None = None,
        ready_states: list[str] | None = None,
    ):
        super().__init__(roi_results=[True, True, True])
        self.result_visible_results = result_visible_results
        self.panel_visible_results = panel_visible_results or []
        self.ready_states = ready_states or [self.MATCH_READY_STATE_READY]
        self.auto_battle_calls = []

    def click_ready_button(self, mode: str, match_index: int) -> str:
        state = self.ready_states.pop(0)
        if state == self.MATCH_READY_STATE_READY:
            self.roi_calls.append(
                (
                    self.BTN_HSLJ_READY_TEMPLATES,
                    self.ROI_READY_BUTTON,
                    self.MATCH_READY_TIMEOUT_MS,
                    "华山论剑准备按钮",
                    0.85,
                    self.MATCH_WAIT_POLL_INTERVAL_MS,
                )
            )
            self.click_offsets.append(0)
            self.wait_calls.append(1000)
        return state

    def is_result_panel_visible(self) -> bool:
        return self.result_visible_results.pop(0)

    def is_hslj_panel_visible(self) -> bool:
        if self.panel_visible_results:
            return self.panel_visible_results.pop(0)
        return False

    def auto_battle(self, interval_ms: int = 500) -> None:
        self.auto_battle_calls.append(interval_ms)


class ReadyWaitHsljTask(HSLJTask):
    def __init__(
        self,
        *,
        confirm_results: list[bool] | None = None,
        ready_results: list[bool] | None = None,
        result_results: list[bool] | None = None,
        match_success_results: list[bool] | None = None,
        panel_results: list[bool] | None = None,
        match_button_results: list[bool] | None = None,
        mode_selected_results: list[bool] | None = None,
        cancel_results: list[bool] | None = None,
    ):
        super().__init__()
        self.confirm_results = confirm_results or []
        self.ready_results = ready_results or []
        self.result_results = result_results or []
        self.match_success_results = match_success_results or []
        self.panel_results = panel_results or []
        self.match_button_results = match_button_results or []
        self.mode_selected_results = mode_selected_results or []
        self.cancel_results = cancel_results or []
        self.wait_calls = []
        self.click_offsets = []
        self.cancel_calls = []
        self.debug_prefixes = []
        self.logs = []

    def confirm_match_leave_team_dialog_if_needed(self, activity_name: str, **kwargs) -> bool:
        return self.confirm_results.pop(0) if self.confirm_results else False

    def is_ready_button_visible(self) -> bool:
        return self.ready_results.pop(0) if self.ready_results else False

    def is_result_panel_visible_quiet(self) -> bool:
        return self.result_results.pop(0) if self.result_results else False

    def is_match_success_visible_quiet(self) -> bool:
        return self.match_success_results.pop(0) if self.match_success_results else False

    def is_hslj_panel_visible_quiet(self) -> bool:
        return self.panel_results.pop(0) if self.panel_results else False

    def is_match_button_visible_quiet(self) -> bool:
        return self.match_button_results.pop(0) if self.match_button_results else False

    def is_hslj_mode_selected_quiet(self, mode: str) -> bool:
        return self.mode_selected_results.pop(0) if self.mode_selected_results else True

    def cancel_current_match(self, mode: str, match_index: int) -> bool:
        self.cancel_calls.append((mode, match_index))
        return self.cancel_results.pop(0) if self.cancel_results else False

    def click(self, offset: int = 3) -> None:
        self.click_offsets.append(offset)

    def wait(self, ms):
        self.wait_calls.append(ms)

    def save_debug_screenshot(self, prefix: str) -> str:
        self.debug_prefixes.append(prefix)
        return f"screenshots/{prefix}.png"

    def _log(self, message: str) -> None:
        self.logs.append(message)


def test_hslj_task_loads_and_is_visible():
    task_file = Path("src/ymjh_bot/task/HSLJ_task.py")

    task_cls = load_task_class(task_file)

    assert task_cls.__name__ == "HSLJTask"
    assert is_visible_task_class(task_cls)
    assert task_cls.task_key == "HSLJ"
    assert task_cls.task_name == "华山论剑"


def test_hslj_activity_open_button_uses_detail_panel_template():
    assert Path(HSLJTask.BTN_HSLJ_ACTIVITY_OPEN).name == "btn_open.png"
    assert HSLJTask.ROI_ACTIVITY_HSLJ_OPEN == (730, 410, 210, 105)
    assert HSLJTask.POINT_ACTIVITY_HSLJ_OPEN == (835, 462)


def test_hslj_step_order():
    steps = HSLJTask.get_steps()
    step_names = [name for name, _, _ in steps]

    assert step_names == [
        "close_all",
        "open_fenzheng_activity",
        "open_panel",
        "complete_1v1",
        "claim_first_win",
        "switch_to_3v3",
        "complete_3v3_matches",
        "final_cleanup",
    ]
    assert steps[0][2]["timeout_ms"] == 120000


def test_hslj_close_all_returns_to_safe_zone_after_cleanup():
    task = FakeHsljTask()

    task.close_all()

    assert task.safe_close_panel_calls == [(5000, 500, None)]
    assert task.wait_calls == [1000]
    assert task.safe_zone_calls == [()]


def test_hslj_close_all_wakes_power_saving_then_returns_to_safe_zone():
    task = FakeHsljTask(power_saving_results=[True])

    task.close_all()

    assert task.clicked_points == [
        (task.POINT_RIGHT_JOYSTICK_CENTER[0], task.POINT_RIGHT_JOYSTICK_CENTER[1], 0)
    ]
    assert task.safe_close_panel_calls == [
        (5000, 500, None),
        (5000, 500, None),
    ]
    assert task.wait_calls == [1000, 1000]
    assert task.safe_zone_calls == [()]


def test_hslj_close_all_continues_when_safe_zone_return_fails():
    task = FakeHsljTask(safe_zone_error=RuntimeError("未找到地图世界按钮"))

    task.close_all()

    assert task.safe_close_panel_calls == [(5000, 500, None)]
    assert task.wait_calls == [1000]
    assert task.safe_zone_calls == [()]
    assert "返回鸡鸣寺安全区未完成，继续从当前界面打开华山论剑：未找到地图世界按钮" in task.logs


def test_hslj_safe_close_panels_collapses_chat_before_and_after():
    task = SafeCloseHsljTask(image_results=[False])

    task.close_all_panels_for_hslj()

    assert task.chat_collapse_calls == [800, 800]
    assert task.image_calls == [
        ([task.BTN_CLOSE, task.BTN_PANE_CLOSE, task.BTN_WELCOME_CLOSE], 5000, 0.8)
    ]
    assert task.click_offsets == []
    assert "已关闭所有弹窗" in task.logs


def test_open_fenzheng_activity_uses_fenzheng_tab_point():
    task = FakeHsljTask()

    task.open_fenzheng_activity()

    assert task.open_activity_calls == [
        ("纷争", None, 30000, 2500, 1500),
    ]


def test_open_panel_clicks_activity_icon_open_button_and_verifies_panel():
    task = FakeHsljTask(roi_results=[True, True, True])

    task.open_panel()

    assert task.roi_calls == [
        (
            task.BTN_HSLJ_ACTIVITY_1V1,
            task.ROI_ACTIVITY_HSLJ_CARD,
            5000,
            "活动页华山论剑卡片",
            0.85,
            500,
        ),
        (
            task.BTN_HSLJ_ACTIVITY_OPEN,
            task.ROI_ACTIVITY_HSLJ_OPEN,
            5000,
            "活动页华山论剑打开按钮",
            0.85,
            500,
        ),
        (
            task.TITLE_HSLJ,
            task.ROI_PANEL_TITLE,
            5000,
            "华山论剑面板",
            0.85,
            500,
        ),
    ]
    assert task.clicked_points == [(task.POINT_ACTIVITY_HSLJ_ICON[0], task.POINT_ACTIVITY_HSLJ_ICON[1], 0)]
    assert task.click_offsets == [0]
    assert task.wait_calls == [1000, 2000]


def test_switch_to_3v3_clicks_panel_tab_and_verifies_panel():
    task = FakeHsljTask(roi_results=[True], find_once_results=[False, False, False, True, True, False])

    task.switch_to_3v3()

    assert task.roi_calls == [
        (task.TITLE_HSLJ, task.ROI_PANEL_TITLE, 10000, "华山论剑面板", 0.85, 500),
    ]
    assert task.clicked_points == [(task.POINT_TAB_3V3[0], task.POINT_TAB_3V3[1], 0)]
    assert task.wait_calls == [1500]
    assert task.find_once_calls == [
        (task.TEXT_HSLJ_EXIT, 0.85, task.scale_roi(task.ROI_RESULT_EXIT_TEXT), False, False),
        (task.BTN_HSLJ_READY_TEMPLATES, 0.85, task.scale_roi(task.ROI_READY_BUTTON), False, False),
        (task.TITLE_HSLJ, 0.85, task.scale_roi(task.ROI_PANEL_TITLE), False, False),
        (task.TITLE_HSLJ, 0.85, task.scale_roi(task.ROI_PANEL_TITLE), False, False),
        (task.TAB_HSLJ_3V3_ACTIVE, 0.85, task.scale_roi(task.ROI_SIDE_TABS), False, False),
        (task.TAB_HSLJ_1V1_ACTIVE, 0.85, task.scale_roi(task.ROI_SIDE_TABS), False, False),
    ]


def test_select_hslj_mode_retries_and_raises_when_active_tab_missing():
    task = ModeSwitchHsljTask(selected_results=[False, False, False])

    with pytest.raises(RuntimeError, match="未确认真实页签"):
        task.select_hslj_mode("3v3")

    assert task.clicked_points == [(task.POINT_TAB_3V3[0], task.POINT_TAB_3V3[1], 0)] * 3
    assert task.wait_calls == [1500, 1500, 1500]
    assert task.debug_prefixes == ["hslj_switch_3v3_failed"]


def test_switch_to_3v3_cancels_residual_non_3v3_match_before_switching():
    task = ResidualSwitchHsljTask()

    task.switch_to_3v3()

    assert task.ready_calls == [("3v3", 10000)]
    assert task.cancel_calls == [("1v1", 0)]
    assert task.selected_modes == ["3v3"]
    assert "切换 3v3 前检测到非 3v3 残留匹配中状态，先取消匹配" in task.logs


def test_complete_1v1_skips_matching_when_reward_already_claimed():
    task = OneVOneFlowTask(complete=True)

    task.complete_1v1()

    assert task.ready_calls == [("1v1", 10000)]
    assert task.selected_modes == ["1v1"]
    assert task.match_clicks == 0
    assert task.battle_calls == []
    assert task.claim_calls == ["1v1"]
    assert "检测到华山论剑 1v1 首胜奖励已领取，跳过匹配" in task.logs


def test_complete_1v1_stops_when_reward_claimed_after_match():
    task = OneVOneFlowTask(claim_results=[False, True])

    task.complete_1v1()

    assert task.ready_calls == [("1v1", 10000)]
    assert task.selected_modes == ["1v1"]
    assert task.match_clicks == 1
    assert task.battle_calls == [("1v1", 1)]
    assert task.claim_calls == ["1v1", "1v1"]


def test_complete_1v1_first_win_continues_until_stopped_when_reward_unclaimed():
    task = OneVOneFlowTask(
        hslj_settings={
            "1v1": {"strategy": "first_win", "count": 1},
            "3v3": {"strategy": "fixed_count", "count": 5},
        },
        claim_results=[False, False, False],
        stop_after_matches=2,
    )

    task.complete_1v1()

    assert task.match_clicks == 2
    assert task.battle_calls == [("1v1", 1), ("1v1", 2)]
    assert task.claim_calls == ["1v1", "1v1", "1v1"]
    assert "华山论剑 1v1 首胜匹配已停止" in task.logs


def test_complete_1v1_first_win_ignores_configured_attempt_limit_until_reward_claimed():
    task = OneVOneFlowTask(
        hslj_settings={
            "1v1": {"strategy": "first_win", "count": 1},
            "3v3": {"strategy": "fixed_count", "count": 5},
        },
        claim_results=[False, False, True],
    )

    task.complete_1v1()

    assert task.match_clicks == 2
    assert task.battle_calls == [("1v1", 1), ("1v1", 2)]
    assert task.claim_calls == ["1v1", "1v1", "1v1"]
    assert "检测到华山论剑 1v1 首胜奖励已领取" in task.logs


def test_complete_1v1_fixed_count_runs_configured_matches():
    task = OneVOneFlowTask(
        hslj_settings={
            "1v1": {"strategy": "fixed_count", "count": 2},
            "3v3": {"strategy": "fixed_count", "count": 5},
        }
    )

    task.complete_1v1()

    assert task.match_clicks == 2
    assert task.battle_calls == [("1v1", 1), ("1v1", 2)]
    assert task.claim_calls == ["1v1", "1v1"]


def test_complete_1v1_infinite_runs_until_stopped():
    task = OneVOneFlowTask(
        hslj_settings={
            "1v1": {"strategy": "infinite", "count": 5},
            "3v3": {"strategy": "fixed_count", "count": 5},
        },
        stop_after_matches=3,
    )

    task.complete_1v1()

    assert task.match_clicks == 3
    assert task.battle_calls == [("1v1", 1), ("1v1", 2), ("1v1", 3)]
    assert task.claim_calls == ["1v1", "1v1", "1v1"]


def test_hslj_click_match_confirms_leave_team_dialog():
    task = FakeHsljTask(roi_results=[True], find_once_results=[False, False, False, True])

    task.click_match_button()

    assert task.roi_calls == [
        (
            task.BTN_HSLJ_MATCH_TEMPLATES,
            task.ROI_MATCH_BUTTON,
            3000,
            "华山论剑匹配按钮",
            0.85,
            500,
        )
    ]
    assert task.clicked_points == []
    assert task.find_once_calls == [
        (
            task.BTN_HSLJ_READY_TEMPLATES,
            0.85,
            task.scale_roi(task.ROI_READY_BUTTON),
            False,
            False,
        ),
        (
            task.TEXT_HSLJ_EXIT,
            0.85,
            task.scale_roi(task.ROI_RESULT_EXIT_TEXT),
            False,
            False,
        ),
        (
            task.TEXT_HSLJ_MATCH_SUCCESS,
            0.85,
            task.scale_roi(task.ROI_MATCH_SUCCESS),
            False,
            False,
        ),
        (
            task.BTN_MODAL_OK,
            0.85,
            task.scale_roi(task.ROI_CENTER_MODAL_OK),
            False,
            False,
        )
    ]
    assert task.click_offsets == [0, 0]
    assert task.wait_calls == [task.MATCH_SETTLE_WAIT_MS, 1200]
    assert "检测到华山论剑单人匹配退队确认，点击确定" in task.logs


def test_hslj_click_match_continues_when_already_matching():
    task = FakeHsljTask(roi_results=[False, True], find_once_results=[False, False, False, False])

    task.click_match_button()

    assert task.roi_calls == [
        (
            task.BTN_HSLJ_MATCH_TEMPLATES,
            task.ROI_MATCH_BUTTON,
            3000,
            "华山论剑匹配按钮",
            0.85,
            500,
        ),
        (
            task.BTN_HSLJ_MATCH_EXIT_TEMPLATES,
            task.ROI_MATCH_BUTTON,
            1200,
            "华山论剑取消匹配按钮",
            0.85,
            300,
        ),
    ]
    assert task.click_offsets == []
    assert task.clicked_points == []
    assert task.find_once_calls == [
        (
            task.BTN_HSLJ_READY_TEMPLATES,
            0.85,
            task.scale_roi(task.ROI_READY_BUTTON),
            False,
            False,
        ),
        (
            task.TEXT_HSLJ_EXIT,
            0.85,
            task.scale_roi(task.ROI_RESULT_EXIT_TEXT),
            False,
            False,
        ),
        (
            task.TEXT_HSLJ_MATCH_SUCCESS,
            0.85,
            task.scale_roi(task.ROI_MATCH_SUCCESS),
            False,
            False,
        ),
        (
            task.BTN_MODAL_OK,
            0.85,
            task.scale_roi(task.ROI_CENTER_MODAL_OK),
            False,
            False,
        )
    ]
    assert "检测到华山论剑已在匹配中，继续等待准备" in task.logs


def test_hslj_click_match_returns_when_already_ready():
    task = FakeHsljTask(find_once_results=[True])

    task.click_match_button()

    assert task.roi_calls == []
    assert task.debug_prefixes == []
    assert task.click_offsets == []
    assert "检测到华山论剑已进入准备态，跳过匹配按钮点击" in task.logs


def test_hslj_click_match_raises_when_state_button_missing():
    task = FakeHsljTask(roi_results=[False, False])

    with pytest.raises(RuntimeError, match="未识别到华山论剑匹配状态按钮"):
        task.click_match_button()

    assert task.roi_calls == [
        (
            task.BTN_HSLJ_MATCH_TEMPLATES,
            task.ROI_MATCH_BUTTON,
            3000,
            "华山论剑匹配按钮",
            0.85,
            500,
        ),
        (
            task.BTN_HSLJ_MATCH_EXIT_TEMPLATES,
            task.ROI_MATCH_BUTTON,
            1200,
            "华山论剑取消匹配按钮",
            0.85,
            300,
        ),
    ]
    assert task.debug_prefixes == ["hslj_match_button_missing"]
    assert task.click_offsets == []
    assert task.clicked_points == []


def test_hslj_cancel_current_match_clicks_exit_and_confirms_panel():
    task = FakeHsljTask(roi_results=[True, True], find_once_results=[False])

    assert task.cancel_current_match("3v3", 2)

    assert task.roi_calls == [
        (
            task.BTN_HSLJ_MATCH_EXIT_TEMPLATES,
            task.ROI_MATCH_BUTTON,
            3000,
            "华山论剑取消匹配按钮",
            0.85,
            300,
        ),
        (
            task.TITLE_HSLJ,
            task.ROI_PANEL_TITLE,
            5000,
            "华山论剑面板",
            0.85,
            500,
        ),
    ]
    assert task.click_offsets == [0]
    assert task.wait_calls == [task.MATCH_SETTLE_WAIT_MS]
    assert task.find_once_calls == [
        (
            task.BTN_MODAL_OK,
            0.85,
            task.scale_roi(task.ROI_CENTER_MODAL_OK),
            False,
            False,
        )
    ]
    assert "华山论剑 3v3 第 2 场已取消匹配并回到面板" in task.logs


def test_hslj_ready_wait_returns_when_match_button_visible_on_panel():
    task = ReadyWaitHsljTask(
        panel_results=[True],
        mode_selected_results=[True],
        match_button_results=[True],
    )

    state = task.click_ready_button("1v1", 1)

    assert state == task.BATTLE_FINISH_RETURNED_PANEL
    assert task.click_offsets == []
    assert task.wait_calls == []
    assert "华山论剑 1v1 第 1 场已回到可匹配面板" in task.logs


def test_hslj_ready_wait_continues_on_match_success_transition():
    task = ReadyWaitHsljTask(
        ready_results=[False, True],
        match_success_results=[True],
    )

    state = task.click_ready_button("3v3", 1)

    assert state == task.MATCH_READY_STATE_READY
    assert task.click_offsets == [0]
    assert task.wait_calls == [task.MATCH_WAIT_POLL_INTERVAL_MS, 1000]
    assert "华山论剑 3v3 第 1 场匹配成功，等待准备/入场" in task.logs


def test_hslj_ready_wait_does_not_return_panel_when_mode_mismatches():
    task = ReadyWaitHsljTask(
        panel_results=[True, True],
        mode_selected_results=[False, True],
        match_button_results=[True],
    )

    state = task.click_ready_button("3v3", 1)

    assert state == task.BATTLE_FINISH_RETURNED_PANEL
    assert task.wait_calls == [task.MATCH_WAIT_POLL_INTERVAL_MS]
    assert "华山论剑 3v3 第 1 场回到面板但当前页签不一致，继续等待" in task.logs


def test_hslj_ready_wait_times_out_cancels_match_and_returns_panel():
    task = ReadyWaitHsljTask(cancel_results=[True])
    task.MATCH_READY_TIMEOUT_MS = 0

    state = task.click_ready_button("3v3", 2)

    assert state == task.BATTLE_FINISH_RETURNED_PANEL
    assert task.debug_prefixes == ["hslj_3v3_2_match_ready_timeout"]
    assert task.cancel_calls == [("3v3", 2)]


def test_hslj_ready_wait_raises_when_timeout_cancel_fails():
    task = ReadyWaitHsljTask(cancel_results=[False])
    task.MATCH_READY_TIMEOUT_MS = 0

    with pytest.raises(RuntimeError, match="取消匹配失败"):
        task.click_ready_button("3v3", 2)

    assert task.debug_prefixes == ["hslj_3v3_2_match_ready_timeout"]
    assert task.cancel_calls == [("3v3", 2)]


def test_claim_first_win_returns_true_when_chest_already_claimed():
    task = ClaimFirstWinHsljTask(reward_state="claimed")

    assert task.claim_first_win_reward("1v1")

    assert task.click_offsets == []
    assert task.clicked_points == []


def test_claim_first_win_clicks_ready_chest_and_verifies_claimed():
    task = ClaimFirstWinHsljTask(reward_state="ready")

    assert task.claim_first_win_reward("1v1")

    assert task.roi_calls == [
        (
            task.ICON_HSLJ_FIRST_WIN_CHEST,
            task.ROI_FIRST_WIN_CHEST,
            2500,
            "华山论剑 1v1 已领取首胜宝箱",
            0.85,
            500,
        )
    ]
    assert task.click_offsets == [0]
    assert task.clicked_points == []
    assert task.wait_calls == [1500]
    assert task.close_reward_calls == [(3, True)]


def test_claim_first_win_initial_chest_does_not_click():
    task = ClaimFirstWinHsljTask(reward_state="initial")

    assert not task.claim_first_win_reward("3v3")

    assert task.click_offsets == []
    assert task.clicked_points == []
    assert "华山论剑 3v3 首胜宝箱尚未可领取" in task.logs


def test_claim_first_win_falls_back_to_fixed_point_when_state_unknown():
    task = ClaimFirstWinHsljTask(reward_state="unknown")

    assert task.claim_first_win_reward("3v3")

    assert task.clicked_points == [(task.POINT_FIRST_WIN_CHEST[0], task.POINT_FIRST_WIN_CHEST[1], 0)]
    assert task.click_offsets == []
    assert task.wait_calls == [1500]
    assert task.roi_calls == [
        (
            task.ICON_HSLJ_FIRST_WIN_CHEST,
            task.ROI_FIRST_WIN_CHEST,
            2500,
            "华山论剑 3v3 已领取首胜宝箱",
            0.85,
            500,
        )
    ]
    assert any("initial=0.200" in log for log in task.logs)


def test_claim_first_win_unknown_state_does_not_click_when_panel_unstable():
    task = ClaimFirstWinHsljTask(reward_state="unknown", panel_visible=False)

    assert not task.claim_first_win_reward("3v3")

    assert task.clicked_points == []
    assert task.click_offsets == []
    assert "当前不在可领取华山论剑 3v3 首胜奖励的稳定面板，跳过领取" in task.logs


def test_3v3_loop_runs_default_five_matches():
    task = ThreeVThreeLoopTask()

    task.complete_3v3_matches()

    assert task.ready_calls == [("3v3", 10000)]
    assert task.selected_modes == ["3v3"]
    assert task.match_clicks == task.DEFAULT_LUNJIAN_COUNT
    assert task.battle_calls == [("3v3", index) for index in range(1, 6)]
    assert task.claim_calls == ["3v3"] * task.DEFAULT_LUNJIAN_COUNT


def test_3v3_loop_uses_configured_match_count():
    task = ThreeVThreeLoopTask(lunjian_count=3)

    task.complete_3v3_matches()

    assert task.match_clicks == 3
    assert task.battle_calls == [("3v3", 1), ("3v3", 2), ("3v3", 3)]
    assert task.claim_calls == ["3v3", "3v3", "3v3"]


def test_3v3_loop_infinite_runs_until_stopped():
    task = ThreeVThreeLoopTask(lunjian_count=2, lunjian_infinite=True, stop_after_matches=3)

    task.complete_3v3_matches()

    assert task.match_clicks == 3
    assert task.battle_calls == [("3v3", 1), ("3v3", 2), ("3v3", 3)]
    assert task.claim_calls == ["3v3", "3v3", "3v3"]


def test_3v3_first_win_runs_until_reward_claimed():
    task = ThreeVThreeLoopTask(
        hslj_settings={
            "1v1": {"strategy": "first_win", "count": 5},
            "3v3": {"strategy": "first_win", "count": 5},
        },
        claim_results=[False, True],
    )

    task.complete_3v3_matches()

    assert task.match_clicks == 1
    assert task.battle_calls == [("3v3", 1)]
    assert task.claim_calls == ["3v3", "3v3"]
    assert "检测到华山论剑 3v3 首胜奖励已领取" in task.logs


def test_run_match_battle_clicks_ready_battles_and_exits_result_panel():
    task = BattleFlowHsljTask(result_visible_results=[False, True], panel_visible_results=[False])

    task.run_match_battle("1v1", 1)

    assert task.roi_calls == [
        (
            task.BTN_HSLJ_READY_TEMPLATES,
            task.ROI_READY_BUTTON,
            task.MATCH_READY_TIMEOUT_MS,
            "华山论剑准备按钮",
            0.85,
            task.MATCH_WAIT_POLL_INTERVAL_MS,
        ),
        (
            task.TEXT_HSLJ_EXIT,
            task.ROI_RESULT_EXIT_TEXT,
            10000,
            "华山论剑结果面板离开按钮",
            0.85,
            500,
        ),
        (
            task.TITLE_HSLJ,
            task.ROI_PANEL_TITLE,
            30000,
            "华山论剑面板",
            0.85,
            500,
        ),
    ]
    assert task.click_offsets == [0, 0]
    assert task.swipe_calls == [(105, 455, 105, 385, task.BATTLE_FORWARD_MS)]
    assert task.auto_battle_calls == [task.AUTO_BATTLE_INTERVAL_MS]
    assert task.wait_calls == [1000, 3000]


def test_run_match_battle_stops_before_auto_battle_when_exit_is_visible():
    task = BattleFlowHsljTask(result_visible_results=[True])

    task.run_match_battle("1v1", 1)

    assert task.roi_calls == [
        (
            task.BTN_HSLJ_READY_TEMPLATES,
            task.ROI_READY_BUTTON,
            task.MATCH_READY_TIMEOUT_MS,
            "华山论剑准备按钮",
            0.85,
            task.MATCH_WAIT_POLL_INTERVAL_MS,
        ),
        (
            task.TEXT_HSLJ_EXIT,
            task.ROI_RESULT_EXIT_TEXT,
            10000,
            "华山论剑结果面板离开按钮",
            0.85,
            500,
        ),
        (
            task.TITLE_HSLJ,
            task.ROI_PANEL_TITLE,
            30000,
            "华山论剑面板",
            0.85,
            500,
        ),
    ]
    assert task.swipe_calls == [(105, 455, 105, 385, task.BATTLE_FORWARD_MS)]
    assert task.auto_battle_calls == []
    assert task.click_offsets == [0, 0]


def test_run_match_battle_stops_auto_battle_when_panel_has_returned():
    task = BattleFlowHsljTask(result_visible_results=[False, False], panel_visible_results=[False, True])

    task.run_match_battle("3v3", 1)

    assert task.roi_calls == [
        (
            task.BTN_HSLJ_READY_TEMPLATES,
            task.ROI_READY_BUTTON,
            task.MATCH_READY_TIMEOUT_MS,
            "华山论剑准备按钮",
            0.85,
            task.MATCH_WAIT_POLL_INTERVAL_MS,
        ),
        (
            task.TITLE_HSLJ,
            task.ROI_PANEL_TITLE,
            30000,
            "华山论剑面板",
            0.85,
            500,
        ),
    ]
    assert task.click_offsets == [0]
    assert task.swipe_calls == [(105, 455, 105, 385, task.BATTLE_FORWARD_MS)]
    assert task.auto_battle_calls == [task.AUTO_BATTLE_INTERVAL_MS]
    assert task.wait_calls == [1000]
