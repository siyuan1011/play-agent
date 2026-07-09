from pathlib import Path

import pytest

from botCore import load_task_class
from botCore.task import StepJumpException
from botCore.vision import load_image
from ymjh_bot.task.PZSY_task import PozhenSheyanTask
from ymjh_bot.ui.task_queue_window import is_visible_task_class


class FakePozhenSheyanTask(PozhenSheyanTask):
    def __init__(
        self,
        roi_results: list[bool] | None = None,
        image_results: list[bool] | None = None,
        click_template_results: list[bool] | None = None,
        start_results: list[bool] | None = None,
        banquet_panel_visible: bool = False,
    ):
        super().__init__()
        self.roi_results = roi_results or []
        self.image_results = image_results or []
        self.click_template_results = click_template_results or []
        self.start_results = start_results or []
        self.banquet_panel_visible = banquet_panel_visible
        self.roi_calls = []
        self.image_calls = []
        self.click_template_calls = []
        self.clicked_points = []
        self.click_count = 0
        self.wait_calls = []
        self.logs = []
        self.closed = 0
        self.opened_activity = 0

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
        return self.image_results.pop(0)

    def click_template_if_available(
        self,
        template,
        *,
        timeout_ms,
        description,
        threshold=0.8,
        wait_after_click_ms=1000,
        roi=None,
    ):
        self.click_template_calls.append((template, timeout_ms, description, threshold, wait_after_click_ms, roi))
        return self.click_template_results.pop(0)

    def is_start_banquet_enabled(self) -> bool:
        return self.start_results.pop(0)

    def is_banquet_panel_visible(self) -> bool:
        return self.banquet_panel_visible

    def close_all_panels(self, *args, **kwargs) -> None:
        self.closed += 1

    def open_activity_panel(self, *args, **kwargs) -> None:
        self.opened_activity += 1

    def click(self, offset: int = 3) -> None:
        self.click_count += 1

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.clicked_points.append((x, y, offset))

    def wait(self, ms):
        self.wait_calls.append(ms)

    def _log(self, message: str) -> None:
        self.logs.append(message)


class ScreenshotPozhenSheyanTask(PozhenSheyanTask):
    def __init__(self, screenshot_path: Path):
        super().__init__()
        self.image = load_image(screenshot_path)
        self.logs = []

    def screenshot(self):
        return self.image

    def _log(self, message: str) -> None:
        self.logs.append(message)


def test_pozhen_sheyan_task_loads_and_is_visible():
    task_file = Path("src/ymjh_bot/task/PZSY_task.py")

    task_cls = load_task_class(task_file)

    assert task_cls.__name__ == "PozhenSheyanTask"
    assert is_visible_task_class(task_cls)
    assert task_cls.task_key == "PZSY"
    assert task_cls.task_name == "破阵设宴"


def test_pozhen_sheyan_step_order():
    steps = [name for name, _, _ in PozhenSheyanTask.get_steps()]

    assert steps == [
        "close_all",
        "open_bangpai_activity",
        "open_pozhen_list",
        "choose_guest",
        "auto_pathfinding",
        "invite_banquet",
        "process_banquet_items",
        "start_banquet_if_ready",
        "verify_completion",
    ]


def test_open_pozhen_list_jumps_to_end_when_entry_missing():
    task = FakePozhenSheyanTask([False])

    with pytest.raises(StepJumpException) as exc_info:
        task.open_pozhen_list()

    assert exc_info.value.target == StepJumpException.JUMP_TO_END
    assert task.click_count == 0
    assert "未找到破阵设宴入口，默认破阵设宴当前不可接取或已完成" in task.logs


def test_open_pozhen_list_clicks_activity_forward_button():
    task = FakePozhenSheyanTask([True, True])

    task.open_pozhen_list()

    assert task.roi_calls == [
        (
            task.BTN_POZHEN_SHEYAN_ENTRY,
            task.ROI_POZHEN_SHEYAN_ENTRY,
            3000,
            "活动页破阵设宴入口",
            0.8,
            500,
        ),
        (
            task.BTN_ACTIVITY_FORWARD,
            task.ROI_POZHEN_SHEYAN_ENTRY,
            5000,
            "活动页破阵设宴前往按钮",
            0.8,
            500,
        ),
    ]
    assert task.click_count == 1
    assert task.wait_calls == [1500]


def test_choose_guest_clicks_invite_forward_button():
    task = FakePozhenSheyanTask([True])

    task.choose_guest()

    assert task.roi_calls == [
        (
            task.BTN_MENKE_INVITE_FORWARD,
            task.ROI_POZHEN_INVITE_BUTTONS,
            10000,
            "破阵列表前往邀约按钮",
            0.8,
            500,
        )
    ]
    assert task.click_count == 1
    assert task.wait_calls == [1500]


def test_choose_guest_jumps_to_items_when_banquet_panel_is_already_open():
    task = FakePozhenSheyanTask(banquet_panel_visible=True)

    with pytest.raises(StepJumpException) as exc_info:
        task.choose_guest()

    assert exc_info.value.target == "process_banquet_items"
    assert task.roi_calls == []
    assert "检测到已在破阵设宴物品面板，跳过邀约流程" in task.logs


def test_invite_banquet_clicks_confirm_invite_and_waits_for_panel():
    task = FakePozhenSheyanTask(image_results=[True, True, True])

    task.invite_banquet()

    assert task.image_calls == [
        (task.BTN_MENKE_BANQUET_INVITE, 120000, 0.8),
        (task.BTN_MENKE_CONFIRM_INVITE, 30000, 0.8),
        (
            [
                task.BTN_POZHEN_GET_ITEM,
                task.BTN_POZHEN_ONE_KEY_SUBMIT,
                task.BTN_POZHEN_SUBMIT_5_TAB,
                task.BTN_POZHEN_SUBMIT_6_TAB,
            ],
            30000,
            0.8,
        ),
    ]
    assert task.click_count == 2
    assert task.wait_calls == [1500, 1500]


def test_process_selected_item_clicks_pozhen_one_key_submit():
    task = FakePozhenSheyanTask(click_template_results=[True])

    task.process_selected_item(1)

    assert task.click_template_calls == [
        (task.BTN_POZHEN_ONE_KEY_SUBMIT, 800, "一键提交按钮", 0.85, 1500, task.ROI_BANQUET_ACTION)
    ]


def test_start_banquet_falls_back_from_six_to_five_dishes():
    task = FakePozhenSheyanTask(click_template_results=[True], start_results=[False, True])

    task.start_banquet_if_ready()

    assert task.clicked_points == [(215, 396, 0), (304, 602, 0)]
    assert task.wait_calls == [800, 1500]
    assert task.click_template_calls == [
        (task.BTN_MODAL_OK, 3000, "开始设宴确认按钮", 0.85, 2000, None)
    ]
    assert task._started_banquet is True


def test_start_banquet_skips_when_six_and_five_are_disabled():
    task = FakePozhenSheyanTask(start_results=[False, False])

    task.start_banquet_if_ready()

    assert task.clicked_points == [(215, 396, 0)]
    assert "物品不足，跳过开始设宴" in task.logs
    assert task._started_banquet is False


def test_pozhen_start_banquet_disabled_references_stay_below_threshold():
    root = Path(__file__).resolve().parents[1]
    prefix = "\u7834\u9635\u8bbe\u5bb4"

    initial_panel = ScreenshotPozhenSheyanTask(root / "screenshots" / f"{prefix}7-1.png")
    submitted_panel = ScreenshotPozhenSheyanTask(root / "screenshots" / f"{prefix}7-2.png")

    assert not initial_panel.is_start_banquet_enabled()
    assert not submitted_panel.is_start_banquet_enabled()


def test_verify_completion_accepts_missing_activity_entry():
    task = FakePozhenSheyanTask(roi_results=[False])

    task.verify_completion()

    assert task.closed == 1
    assert task.opened_activity == 1
    assert "完成验证：活动页已无破阵设宴入口" in task.logs


def test_verify_completion_raises_when_started_but_invite_still_available():
    task = FakePozhenSheyanTask(roi_results=[True, True, True], banquet_panel_visible=False)
    task._started_banquet = True

    with pytest.raises(RuntimeError, match="仍可前往邀约"):
        task.verify_completion()

    assert task.click_count == 1
