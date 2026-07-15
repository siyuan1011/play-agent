from pathlib import Path

import pytest

from botCore import load_task_class
from ymjh_bot.task.JHYXB_task import JianghuYingxiongbangTask
from ymjh_bot.ui.task_queue_window import is_visible_task_class


class FakeJhyxbTask(JianghuYingxiongbangTask):
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
        self.safe_zone_error = safe_zone_error
        self.roi_calls = []
        self.image_calls = []
        self.find_once_calls = []
        self.open_activity_calls = []
        self.close_panel_calls = []
        self.clicked_points = []
        self.click_offsets = []
        self.swipe_calls = []
        self.wait_calls = []
        self.safe_zone_calls = []
        self.debug_prefixes = []
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
        return self.roi_results.pop(0)

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

    def close_all_panels(
        self,
        templates=None,
        *,
        timeout_ms=5000,
        wait_after_click_ms=500,
        max_attempts=None,
    ):
        self.close_panel_calls.append((templates, timeout_ms, wait_after_click_ms, max_attempts))

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


class SafeCloseJhyxbTask(JianghuYingxiongbangTask):
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


class LoopOnlyJhyxbTask(JianghuYingxiongbangTask):
    def __init__(self, challenge_zero_results: list[bool] | None = None):
        super().__init__()
        self.challenge_zero_results = challenge_zero_results or []
        self.ready_calls = []
        self.match_clicks = 0
        self.battle_matches = []
        self.battle_deadlines = []

    def ensure_jhyxb_panel_ready(self, *, timeout_ms: int) -> None:
        self.ready_calls.append(timeout_ms)

    def click_match_button(self) -> float:
        self.match_clicks += 1
        return float(self.match_clicks)

    def is_challenge_count_zero(self) -> bool:
        if self.challenge_zero_results:
            return self.challenge_zero_results.pop(0)
        return False

    def run_match_battle(self, match_index: int, *, match_deadline: float | None = None) -> None:
        self.battle_matches.append(match_index)
        self.battle_deadlines.append(match_deadline)

    def _log(self, message: str) -> None:
        pass


class BattleFlowJhyxbTask(FakeJhyxbTask):
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

    def click_ready_button(self, match_index: int, *, deadline: float | None = None) -> str:
        state = self.ready_states.pop(0)
        if state == self.MATCH_READY_STATE_READY:
            self.roi_calls.append(
                (
                    self.BTN_JHYXB_READY,
                    self.ROI_READY_BUTTON,
                    self.MATCH_READY_TIMEOUT_MS,
                    "江湖英雄榜准备按钮",
                    0.85,
                    self.MATCH_WAIT_POLL_INTERVAL_MS,
                )
            )
            self._battle_result_deadline = self._make_deadline(self.RESULT_TIMEOUT_MS)
            self.click_offsets.append(0)
            self.wait_calls.append(1000)
        return state

    def is_result_panel_visible(self) -> bool:
        return self.result_visible_results.pop(0)

    def is_jhyxb_panel_visible(self) -> bool:
        if self.panel_visible_results:
            return self.panel_visible_results.pop(0)
        return False

    def auto_battle(self, interval_ms: int = 500) -> None:
        self.auto_battle_calls.append(interval_ms)


class ReadyWaitJhyxbTask(JianghuYingxiongbangTask):
    def __init__(
        self,
        *,
        confirm_results: list[bool] | None = None,
        ready_results: list[bool] | None = None,
        result_results: list[bool] | None = None,
        panel_results: list[bool] | None = None,
        challenge_zero_results: list[bool] | None = None,
        match_button_results: list[bool] | None = None,
    ):
        super().__init__()
        self.confirm_results = confirm_results or []
        self.ready_results = ready_results or []
        self.result_results = result_results or []
        self.panel_results = panel_results or []
        self.challenge_zero_results = challenge_zero_results or []
        self.match_button_results = match_button_results or []
        self.confirm_calls = []
        self.wait_calls = []
        self.click_offsets = []
        self.debug_prefixes = []
        self.logs = []

    def confirm_match_leave_team_dialog_if_needed(self, activity_name: str, **kwargs) -> bool:
        self.confirm_calls.append(activity_name)
        return self.confirm_results.pop(0) if self.confirm_results else False

    def is_ready_button_visible(self) -> bool:
        return self.ready_results.pop(0) if self.ready_results else False

    def is_result_panel_visible_quiet(self) -> bool:
        return self.result_results.pop(0) if self.result_results else False

    def is_jhyxb_panel_visible_quiet(self) -> bool:
        return self.panel_results.pop(0) if self.panel_results else False

    def is_challenge_count_zero_quiet(self) -> bool:
        return self.challenge_zero_results.pop(0) if self.challenge_zero_results else False

    def is_match_button_visible_quiet(self) -> bool:
        return self.match_button_results.pop(0) if self.match_button_results else False

    def click(self, offset: int = 3) -> None:
        self.click_offsets.append(offset)

    def wait(self, ms):
        self.wait_calls.append(ms)

    def save_debug_screenshot(self, prefix: str) -> str:
        self.debug_prefixes.append(prefix)
        return f"screenshots/{prefix}.png"

    def _log(self, message: str) -> None:
        self.logs.append(message)


class MatchDeadlineTrackingJhyxbTask(FakeJhyxbTask):
    def __init__(self):
        super().__init__(roi_results=[False])
        self.events = []

    def _make_deadline(self, timeout_ms: int | None) -> float | None:
        self.events.append(("deadline", timeout_ms))
        return super()._make_deadline(timeout_ms)

    def wait(self, ms):
        self.events.append(("wait", ms))
        super().wait(ms)

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.events.append(("click", x, y, offset))
        super().click_point(x, y, offset)


class ReadyDeadlineTrackingJhyxbTask(ReadyWaitJhyxbTask):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.deadline_timeouts = []
        self.events = []

    def _make_deadline(self, timeout_ms: int | None) -> float | None:
        self.deadline_timeouts.append(timeout_ms)
        self.events.append(("deadline", timeout_ms))
        return super()._make_deadline(timeout_ms)

    def click(self, offset: int = 3) -> None:
        self.events.append(("click", offset))
        super().click(offset)


def test_jhyxb_task_loads_and_is_visible():
    task_file = Path("src/ymjh_bot/task/JHYXB_task.py")

    task_cls = load_task_class(task_file)

    assert task_cls.__name__ == "JianghuYingxiongbangTask"
    assert is_visible_task_class(task_cls)
    assert task_cls.task_key == "JHYXB"
    assert task_cls.task_name == "江湖英雄榜"


def test_jhyxb_step_order():
    steps = JianghuYingxiongbangTask.get_steps()
    step_names = [name for name, _, _ in steps]

    assert step_names == [
        "open_fenzheng_activity",
        "open_jhyxb_panel",
        "use_all_challenges",
        "claim_first_battle_chest",
    ]


def test_jhyxb_match_and_battle_timeouts_are_separate_without_total_step_timeout():
    steps = dict((name, metadata) for name, _, metadata in JianghuYingxiongbangTask.get_steps())

    assert JianghuYingxiongbangTask.MATCH_READY_TIMEOUT_MS == 60 * 1000
    assert JianghuYingxiongbangTask.RESULT_TIMEOUT_MS == 6 * 60 * 1000
    assert steps["use_all_challenges"]["timeout_ms"] is None


def test_jhyxb_safe_close_panels_collapses_chat_before_and_after():
    task = SafeCloseJhyxbTask(image_results=[False])

    task.close_all_panels()

    assert task.chat_collapse_calls == [800, 800]
    assert task.image_calls == [
        ([task.BTN_CLOSE, task.BTN_PANE_CLOSE, task.BTN_WELCOME_CLOSE], 5000, 0.8)
    ]
    assert task.click_offsets == []
    assert "已关闭所有弹窗" in task.logs


def test_on_start_wakes_power_saving_with_right_joystick_center():
    task = FakeJhyxbTask(power_saving_results=[True])

    task.on_start()

    assert task.clicked_points == [
        (task.POINT_RIGHT_JOYSTICK_CENTER[0], task.POINT_RIGHT_JOYSTICK_CENTER[1], 0)
    ]
    assert task.close_panel_calls == [
        (None, 5000, 500, None),
        (None, 5000, 500, None),
    ]
    assert task.wait_calls == [1000, 1000]
    assert task.safe_zone_calls == [()]
    assert "检测到省电模式，点击右下角摇杆中心唤醒" in task.logs


def test_on_start_returns_to_safe_zone_after_cleanup():
    task = FakeJhyxbTask()

    task.on_start()

    assert task.close_panel_calls == [(None, 5000, 500, None)]
    assert task.wait_calls == [1000]
    assert task.safe_zone_calls == [()]


def test_on_start_continues_when_safe_zone_return_fails():
    task = FakeJhyxbTask(safe_zone_error=RuntimeError("未找到地图世界按钮"))

    task.on_start()

    assert task.close_panel_calls == [(None, 5000, 500, None)]
    assert task.wait_calls == [1000]
    assert task.safe_zone_calls == [()]
    assert "返回鸡鸣寺安全区未完成，继续从当前界面打开江湖英雄榜：未找到地图世界按钮" in task.logs


def test_open_fenzheng_activity_uses_fenzheng_tab_point():
    task = FakeJhyxbTask()

    task.open_fenzheng_activity()

    assert task.open_activity_calls == [
        ("纷争", None, 30000, 2500, 1500),
    ]


def test_open_jhyxb_panel_clicks_activity_entry_and_verifies_panel():
    task = FakeJhyxbTask(roi_results=[True, True])

    task.open_jhyxb_panel()

    assert task.roi_calls == [
        (
            task.BTN_JHYXB_ACTIVITY_OPEN,
            task.ROI_ACTIVITY_JHYXB,
            5000,
            "活动页江湖英雄榜打开按钮",
            0.85,
            500,
        ),
        (
            task.TITLE_JHYXB,
            task.ROI_PANEL_TITLE,
            5000,
            "江湖英雄榜面板",
            0.85,
            500,
        ),
    ]
    assert task.click_offsets == [0]
    assert task.wait_calls == [2000]


def test_use_all_challenges_runs_default_five_matches():
    task = LoopOnlyJhyxbTask()

    task.use_all_challenges()

    assert task.ready_calls == [10000] * task.DEFAULT_CHALLENGE_COUNT
    assert task.match_clicks == task.DEFAULT_CHALLENGE_COUNT
    assert task.battle_matches == [1, 2, 3, 4, 5]
    assert task.battle_deadlines == [1.0, 2.0, 3.0, 4.0, 5.0]


def test_use_all_challenges_stops_when_challenge_count_is_zero():
    task = LoopOnlyJhyxbTask(challenge_zero_results=[False, False, True])

    task.use_all_challenges()

    assert task.ready_calls == [10000, 10000, 10000]
    assert task.match_clicks == 2
    assert task.battle_matches == [1, 2]


def test_jhyxb_click_match_starts_deadline_without_fixed_settle_wait():
    task = MatchDeadlineTrackingJhyxbTask()

    deadline = task.click_match_button()

    assert deadline is not None
    assert task.clicked_points == [(task.POINT_JHYXB_MATCH[0], task.POINT_JHYXB_MATCH[1], 0)]
    assert task.events == [
        ("click", task.POINT_JHYXB_MATCH[0], task.POINT_JHYXB_MATCH[1], 0),
        ("deadline", task.MATCH_READY_TIMEOUT_MS),
    ]
    assert task.wait_calls == []


def test_jhyxb_ready_wait_returns_when_panel_has_match_button():
    task = ReadyWaitJhyxbTask(
        panel_results=[True],
        challenge_zero_results=[False],
        match_button_results=[True],
    )

    state = task.click_ready_button(2)

    assert state == task.BATTLE_FINISH_RETURNED_PANEL
    assert task.click_offsets == []
    assert task.wait_calls == []
    assert "第 2 次匹配已回到江湖英雄榜面板" in task.logs


def test_jhyxb_ready_wait_handles_leave_team_dialog_before_ready():
    task = ReadyWaitJhyxbTask(confirm_results=[True, False], ready_results=[True])

    state = task.click_ready_button(1)

    assert state == task.MATCH_READY_STATE_READY
    assert task.confirm_calls == ["江湖英雄榜", "江湖英雄榜"]
    assert task.click_offsets == [0]
    assert task.wait_calls == [1000]


def test_jhyxb_ready_click_starts_six_minute_battle_deadline():
    task = ReadyDeadlineTrackingJhyxbTask(ready_results=[True])
    match_deadline = task._make_deadline(task.MATCH_READY_TIMEOUT_MS)
    task.deadline_timeouts.clear()
    task.events.clear()

    state = task.click_ready_button(1, deadline=match_deadline)

    assert state == task.MATCH_READY_STATE_READY
    assert task.deadline_timeouts == [task.RESULT_TIMEOUT_MS]
    assert task.events == [
        ("click", 0),
        ("deadline", task.RESULT_TIMEOUT_MS),
    ]
    assert task.click_offsets == [0]


def test_jhyxb_ready_wait_times_out_with_debug_screenshot():
    task = ReadyWaitJhyxbTask()
    task.MATCH_READY_TIMEOUT_MS = 0

    with pytest.raises(RuntimeError, match="匹配/准备等待超时"):
        task.click_ready_button(3)

    assert task.debug_prefixes == ["jhyxb_match_3_ready_timeout"]


def test_run_match_battle_skips_result_exit_when_exit_template_is_not_configured():
    task = BattleFlowJhyxbTask(result_visible_results=[False, True], panel_visible_results=[False])

    task.run_match_battle(1)

    assert task.roi_calls == [
        (
            task.BTN_JHYXB_READY,
            task.ROI_READY_BUTTON,
            task.MATCH_READY_TIMEOUT_MS,
            "江湖英雄榜准备按钮",
            0.85,
            task.MATCH_WAIT_POLL_INTERVAL_MS,
        ),
        (
            task.TITLE_JHYXB,
            task.ROI_PANEL_TITLE,
            30000,
            "江湖英雄榜面板",
            0.85,
            500,
        ),
    ]
    assert task.click_offsets == [0]
    assert task.swipe_calls == [(105, 455, 105, 385, task.BATTLE_FORWARD_MS)]
    assert task.auto_battle_calls == [task.AUTO_BATTLE_INTERVAL_MS]
    assert task.wait_calls == [1000]
    assert "结果面板退出按钮模板尚未配置，跳过模板点击" in task.logs


def test_run_match_battle_stops_auto_battle_when_panel_has_returned():
    task = BattleFlowJhyxbTask(result_visible_results=[False, False], panel_visible_results=[False, True])

    task.run_match_battle(1)

    assert task.roi_calls == [
        (
            task.BTN_JHYXB_READY,
            task.ROI_READY_BUTTON,
            task.MATCH_READY_TIMEOUT_MS,
            "江湖英雄榜准备按钮",
            0.85,
            task.MATCH_WAIT_POLL_INTERVAL_MS,
        ),
        (
            task.TITLE_JHYXB,
            task.ROI_PANEL_TITLE,
            30000,
            "江湖英雄榜面板",
            0.85,
            500,
        ),
    ]
    assert task.click_offsets == [0]
    assert task.swipe_calls == [(105, 455, 105, 385, task.BATTLE_FORWARD_MS)]
    assert task.auto_battle_calls == [task.AUTO_BATTLE_INTERVAL_MS]
    assert task.wait_calls == [1000]


def test_jhyxb_run_match_battle_skips_battle_when_panel_returned_before_ready():
    task = BattleFlowJhyxbTask(
        result_visible_results=[],
        ready_states=[JianghuYingxiongbangTask.BATTLE_FINISH_RETURNED_PANEL],
    )

    task.run_match_battle(1)

    assert task.roi_calls == [
        (
            task.TITLE_JHYXB,
            task.ROI_PANEL_TITLE,
            30000,
            "江湖英雄榜面板",
            0.85,
            500,
        ),
    ]
    assert task.click_offsets == []
    assert task.swipe_calls == []
    assert task.auto_battle_calls == []
    assert task.wait_calls == []


def test_claim_first_battle_chest_clicks_ready_chest_and_confirms_claimed_state():
    task = FakeJhyxbTask(
        roi_results=[True, True, True],
        image_results=[False],
        find_once_results=[False, True],
    )

    assert task.claim_first_battle_chest() is True

    assert task.find_once_calls == [
        (
            task.ICON_JHYXB_FIRST_WIN_CHEST,
            0.85,
            task.scale_roi(task.ROI_FIRST_BATTLE_CHEST),
            False,
            False,
        ),
        (
            task.ICON_JHYXB_FIRST_WIN_READY,
            0.85,
            task.scale_roi(task.ROI_FIRST_BATTLE_CHEST),
            False,
            False,
        ),
    ]
    assert task.roi_calls == [
        (task.TITLE_JHYXB, task.ROI_PANEL_TITLE, 10000, "江湖英雄榜面板", 0.85, 500),
        (task.TITLE_JHYXB, task.ROI_PANEL_TITLE, 10000, "江湖英雄榜面板", 0.85, 500),
        (
            task.ICON_JHYXB_FIRST_WIN_CHEST,
            task.ROI_FIRST_BATTLE_CHEST,
            2500,
            "江湖英雄榜已领取首战宝箱",
            0.85,
            500,
        ),
    ]
    assert task.click_offsets == [0]
    assert task.clicked_points == [
        (task.POINT_FIRST_BATTLE_REWARD_DIALOG_DISMISS[0], task.POINT_FIRST_BATTLE_REWARD_DIALOG_DISMISS[1], 0)
    ]
    assert task.wait_calls == [1500, 1000]
    assert "江湖英雄榜首战宝箱领取完成" in task.logs


def test_claim_first_battle_chest_skips_already_claimed_chest():
    task = FakeJhyxbTask(roi_results=[True], find_once_results=[True])

    assert task.claim_first_battle_chest() is True

    assert task.click_offsets == []
    assert task.clicked_points == []
    assert task.wait_calls == []
    assert "江湖英雄榜首战宝箱已领取" in task.logs


def test_claim_first_battle_chest_skips_initial_chest():
    task = FakeJhyxbTask(roi_results=[True], find_once_results=[False, False, True])

    assert task.claim_first_battle_chest() is False

    assert task.click_offsets == []
    assert task.clicked_points == []
    assert task.wait_calls == []
    assert "江湖英雄榜首战宝箱尚未达成，跳过领取" in task.logs


def test_claim_first_battle_chest_uses_safe_point_fallback_for_unknown_state():
    task = FakeJhyxbTask(
        roi_results=[True, True, True],
        image_results=[False],
        find_once_results=[False, False, False, True],
    )

    assert task.claim_first_battle_chest() is True

    assert task.debug_prefixes == ["jhyxb_first_battle_reward_unknown"]
    assert task.clicked_points == [
        (task.POINT_FIRST_BATTLE_CHEST[0], task.POINT_FIRST_BATTLE_CHEST[1], 0),
        (task.POINT_FIRST_BATTLE_REWARD_DIALOG_DISMISS[0], task.POINT_FIRST_BATTLE_REWARD_DIALOG_DISMISS[1], 0),
    ]
    assert "首战宝箱状态未知，使用保底坐标尝试领取" in task.logs


def test_claim_first_battle_chest_raises_when_claim_is_not_confirmed():
    task = FakeJhyxbTask(
        roi_results=[True, False],
        image_results=[False],
        find_once_results=[False, True],
    )

    with pytest.raises(RuntimeError, match="领取后未确认已领取状态"):
        task.claim_first_battle_chest()

    assert task.debug_prefixes == ["jhyxb_first_battle_reward_claim_failed"]
