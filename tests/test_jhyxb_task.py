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
        self.close_panel_calls = []
        self.safe_close_panel_calls = []
        self.clicked_points = []
        self.click_offsets = []
        self.swipe_calls = []
        self.wait_calls = []
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

    def close_all_panels(self, templates=None, *, timeout_ms=5000, wait_after_click_ms=500):
        self.close_panel_calls.append((templates, timeout_ms, wait_after_click_ms))

    def close_all_panels_for_jhyxb(
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

    def ensure_jhyxb_panel_ready(self, *, timeout_ms: int) -> None:
        self.ready_calls.append(timeout_ms)

    def click_match_button(self) -> None:
        self.match_clicks += 1

    def is_challenge_count_zero(self) -> bool:
        if self.challenge_zero_results:
            return self.challenge_zero_results.pop(0)
        return False

    def run_match_battle(self, match_index: int) -> None:
        self.battle_matches.append(match_index)

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

    def click_ready_button(self, match_index: int) -> str:
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
            self.click_offsets.append(0)
            self.wait_calls.append(1000)
        return state

    def is_result_panel_visible(self) -> bool:
        return self.result_visible_results.pop(0)

    def is_jhyxb_panel_visible(self) -> bool:
        if self.panel_visible_results:
            return self.panel_visible_results.pop(0)
        return False

    def auto_battle(self, skill_pages: int = 2, repeat_count: int = 3, interval_ms: int = 500) -> None:
        self.auto_battle_calls.append((skill_pages, repeat_count, interval_ms))


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
        self.wait_calls = []
        self.click_offsets = []
        self.debug_prefixes = []
        self.logs = []

    def confirm_match_leave_team_dialog_if_needed(self, activity_name: str, **kwargs) -> bool:
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


def test_jhyxb_task_loads_and_is_visible():
    task_file = Path("src/ymjh_bot/task/JHYXB_task.py")

    task_cls = load_task_class(task_file)

    assert task_cls.__name__ == "JianghuYingxiongbangTask"
    assert is_visible_task_class(task_cls)
    assert task_cls.task_key == "JHYXB"
    assert task_cls.task_name == "江湖英雄榜"


def test_jhyxb_step_order():
    steps = [name for name, _, _ in JianghuYingxiongbangTask.get_steps()]

    assert steps == [
        "close_all",
        "open_fenzheng_activity",
        "open_jhyxb_panel",
        "use_all_challenges",
        "claim_first_battle_chest",
    ]


def test_jhyxb_safe_close_panels_collapses_chat_before_and_after():
    task = SafeCloseJhyxbTask(image_results=[False])

    task.close_all_panels_for_jhyxb()

    assert task.chat_collapse_calls == [800, 800]
    assert task.image_calls == [
        ([task.BTN_CLOSE, task.BTN_PANE_CLOSE, task.BTN_WELCOME_CLOSE], 5000, 0.8)
    ]
    assert task.click_offsets == []
    assert "已关闭所有弹窗" in task.logs


def test_close_all_wakes_power_saving_with_right_joystick_center():
    task = FakeJhyxbTask(power_saving_results=[True])

    task.close_all()

    assert task.clicked_points == [
        (task.POINT_RIGHT_JOYSTICK_CENTER[0], task.POINT_RIGHT_JOYSTICK_CENTER[1], 0)
    ]
    assert task.safe_close_panel_calls == [
        (5000, 500, None),
        (5000, 500, None),
    ]
    assert task.wait_calls == [1000, 1000]
    assert "检测到省电模式，点击右下角摇杆中心唤醒" in task.logs


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


def test_use_all_challenges_stops_when_challenge_count_is_zero():
    task = LoopOnlyJhyxbTask(challenge_zero_results=[False, False, True])

    task.use_all_challenges()

    assert task.ready_calls == [10000, 10000, 10000]
    assert task.match_clicks == 2
    assert task.battle_matches == [1, 2]


def test_jhyxb_click_match_confirms_leave_team_dialog():
    task = FakeJhyxbTask(roi_results=[False], find_once_results=[True])

    task.click_match_button()

    assert task.clicked_points == [(task.POINT_JHYXB_MATCH[0], task.POINT_JHYXB_MATCH[1], 0)]
    assert task.find_once_calls == [
        (
            task.BTN_MODAL_OK,
            0.85,
            task.scale_roi(task.ROI_CENTER_MODAL_OK),
            False,
            False,
        )
    ]
    assert task.click_offsets == [0]
    assert task.wait_calls == [task.MATCH_SETTLE_WAIT_MS, 1200]
    assert "检测到江湖英雄榜单人匹配退队确认，点击确定" in task.logs


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


def test_jhyxb_ready_wait_times_out_with_debug_screenshot():
    task = ReadyWaitJhyxbTask()
    task.MATCH_READY_TIMEOUT_MS = 0

    with pytest.raises(RuntimeError, match="匹配/准备等待超时"):
        task.click_ready_button(3)

    assert task.debug_prefixes == ["jhyxb_match_3_ready_timeout"]


def test_run_match_battle_clicks_ready_walks_battles_and_exits_result_panel():
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
            task.BTN_JHYXB_RESULT_EXIT,
            task.ROI_RESULT_EXIT_BUTTON,
            10000,
            "江湖英雄榜结果面板退出按钮",
            0.85,
            500,
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
    assert task.click_offsets == [0, 0]
    assert task.swipe_calls == [(105, 455, 105, 385, task.BATTLE_FORWARD_MS)]
    assert task.auto_battle_calls == [(1, 1, task.AUTO_BATTLE_INTERVAL_MS)]
    assert task.wait_calls == [1000, 3000]


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
    assert task.auto_battle_calls == [(1, 1, task.AUTO_BATTLE_INTERVAL_MS)]
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


def test_claim_first_battle_chest_clicks_template_and_closes_confirm_dialog():
    task = FakeJhyxbTask(roi_results=[True, True], image_results=[True, False, False])

    task.claim_first_battle_chest()

    assert task.roi_calls == [
        (
            task.TITLE_JHYXB,
            task.ROI_PANEL_TITLE,
            10000,
            "江湖英雄榜面板",
            0.85,
            500,
        ),
        (
            task.ICON_JHYXB_FIRST_CHEST,
            task.ROI_FIRST_BATTLE_CHEST,
            3000,
            "每日首战宝箱",
            0.85,
            500,
        ),
    ]
    assert task.click_offsets == [0, 0]
    assert task.wait_calls == [1500, 1000]


def test_claim_first_battle_chest_uses_fixed_point_when_template_missing():
    task = FakeJhyxbTask(roi_results=[True, False])

    task.claim_first_battle_chest()

    assert task.clicked_points == [
        (task.POINT_FIRST_BATTLE_CHEST[0], task.POINT_FIRST_BATTLE_CHEST[1], 0),
    ]
    assert task.click_offsets == []
    assert task.wait_calls == [1500]
