import pytest

from ymjh_bot.task.MRYG_task import MRYGTask


class FakeMRYGTask(MRYGTask):
    def __init__(
        self,
        *,
        appear_results: list[bool],
        appear_centers: list[tuple[int, int]] | None = None,
        appear_false_callbacks: dict[str, int] | None = None,
        missing_results: list[bool] | None = None,
        missing_found_centers: list[tuple[int, int]] | None = None,
    ):
        super().__init__()
        self.appear_results = appear_results
        self.appear_centers = appear_centers or []
        self.appear_false_callbacks = appear_false_callbacks or {}
        self.missing_results = missing_results or []
        self.missing_found_centers = missing_found_centers or []
        self.appear_calls = []
        self.missing_calls = []
        self.actions = []
        self.wait_calls = []

    def wait_image_appear(self, template, timeout_ms=10000, threshold=0.8, callback=None, interval_ms=500):
        self.appear_calls.append((template, timeout_ms, threshold, interval_ms))
        if callback:
            for _ in range(self.appear_false_callbacks.get(template, 0)):
                callback(False)
        result = self.appear_results.pop(0)
        if result and self.appear_centers:
            self._last_match_center = self.appear_centers.pop(0)
        elif not result:
            self._last_match_center = None
        if callback:
            callback(result)
        return result

    def wait_image_missing(
        self,
        template,
        timeout_ms=10000,
        threshold=0.8,
        missing_threshold=3,
        callback=None,
        interval_ms=500,
    ):
        self.missing_calls.append((template, timeout_ms, threshold, missing_threshold, interval_ms))
        result = self.missing_results.pop(0)
        if callback and self.missing_found_centers:
            self._last_match_center = self.missing_found_centers.pop(0)
            callback(True, 0)
        return result

    def click(self, offset: int = 3) -> None:
        self.actions.append(("click", self._last_match_center, offset))

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.actions.append(("point", x, y, offset))

    def wait(self, ms):
        self.wait_calls.append(ms)


def test_enter_panel_waits_three_minutes_for_fortune_button():
    task = FakeMRYGTask(appear_results=[False])

    with pytest.raises(RuntimeError, match="未找到算命占卜按钮"):
        task.enter_panel()

    assert task.appear_calls[0] == ([task.BTN_SMZB, task.BTN_OK], 180000, 0.8, 500)
    assert task.actions == []


def test_enter_panel_clicks_template_match_before_fixed_points():
    smzb_center = (1096, 463)
    smzb_retry_center = (1096, 462)
    ttym_center = (297, 555)
    jsgx_center = (737, 618)
    modal_ok_center = (851, 510)
    task = FakeMRYGTask(
        appear_results=[True, True, True, True],
        appear_centers=[smzb_center, ttym_center, jsgx_center, modal_ok_center],
        appear_false_callbacks={MRYGTask.BTN_JSGX: 2},
        missing_results=[True, True],
        missing_found_centers=[smzb_retry_center],
    )

    task.enter_panel()

    assert task.actions[:2] == [
        ("click", smzb_center, 3),
        ("click", smzb_retry_center, 3),
    ]
    ttym_index = task.actions.index(("click", ttym_center, 3))
    assert task.actions[ttym_index : ttym_index + 2] == [
        ("click", ttym_center, 3),
        ("point", 1024, 580, 3),
    ]
    assert task.actions[ttym_index + 2] == ("point", 1024, 580, 3)
    assert ("point", task.POINT_ANSWER[0], task.POINT_ANSWER[1], 3) not in task.actions
    assert (task.BTN_JSGX, 180000, 0.8, 1500) in task.appear_calls
    assert ("click", jsgx_center, 3) in task.actions
    assert ("click", modal_ok_center, 3) in task.actions


def test_enter_panel_does_not_click_fixed_points_when_ttym_is_missing():
    task = FakeMRYGTask(
        appear_results=[True, False],
        appear_centers=[(1096, 463)],
        missing_results=[True],
    )

    with pytest.raises(RuntimeError, match="未找到听天由命按钮"):
        task.enter_panel()

    assert ("point", 1024, 580, 3) not in task.actions
    assert ("point", task.POINT_ANSWER[0], task.POINT_ANSWER[1], 3) not in task.actions


def test_enter_panel_stops_when_required_later_button_is_missing():
    task = FakeMRYGTask(
        appear_results=[True, True, False],
        appear_centers=[(1096, 463), (297, 555)],
        appear_false_callbacks={MRYGTask.BTN_JSGX: 1},
        missing_results=[True],
    )

    with pytest.raises(RuntimeError, match="听天由命后未出现接受卦象按钮"):
        task.enter_panel()

    assert ("point", 1024, 580, 3) in task.actions


def test_enter_panel_does_not_wait_for_ttym_to_disappear():
    task = FakeMRYGTask(
        appear_results=[True, True, True, True],
        appear_centers=[(1096, 463), (297, 555), (737, 618), (851, 510)],
        missing_results=[True, True],
    )

    task.enter_panel()

    assert all(call[0] != task.BTN_TTYM for call in task.missing_calls)
    assert ("point", 1024, 580, 3) not in task.actions
