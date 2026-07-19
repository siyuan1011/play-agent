from __future__ import annotations

import pytest

from ymjh_bot.task.PZSY_task import PZSYTask
from ymjh_bot.task.banquet import (
    BanquetAcquireMixin,
    StallPurchaseCancelError,
    StallPurchaseConfirmationError,
)


CONFIRM_CENTER = (852, 508)
CANCEL_CENTER = (422, 508)


class FakePurchaseTask(BanquetAcquireMixin):
    BTN_MODAL_OK = "btn_modal_ok.png"

    def __init__(
        self,
        *,
        success_on_confirm_attempt: int | None,
        dialog_visible: bool = True,
        cancel_succeeds: bool = True,
    ) -> None:
        self.success_on_confirm_attempt = success_on_confirm_attempt
        self.dialog_visible = dialog_visible
        self.cancel_succeeds = cancel_succeeds
        self.confirm_clicks = 0
        self.cancel_clicks = 0
        self.elapsed_ms = 0
        self.clicks: list[tuple[int, tuple[int, int] | None]] = []
        self.screenshot_prefixes: list[str] = []
        self.logs: list[str] = []
        self._last_match_center: tuple[int, int] | None = None
        self._last_match_score = 0.0

    def wait_image_appear(self, template, **kwargs) -> bool:
        if self.dialog_visible:
            self._last_match_center = CONFIRM_CENTER
            return True
        self._last_match_center = None
        return False

    def wait_image_missing(
        self,
        template,
        *,
        timeout_ms: int,
        callback=None,
        interval_ms: int,
        **kwargs,
    ) -> bool:
        remaining_ms = timeout_ms
        while remaining_ms > 0:
            found = self.dialog_visible
            self._last_match_center = CONFIRM_CENTER if found else None
            if not found:
                return True
            if callback:
                callback(True, 0)
            wait_ms = min(interval_ms, remaining_ms)
            self.wait(wait_ms)
            remaining_ms -= wait_ms
        return False

    def find_image(self, template, *, roi=None, **kwargs) -> bool:
        if template != self.BTN_MODAL_CANCEL or not self.dialog_visible:
            self._last_match_center = None
            return False
        self._last_match_center = CANCEL_CENTER
        return True

    def scale_roi(self, roi):
        return roi

    def click(self, offset: int = 3) -> None:
        self.clicks.append((self.elapsed_ms, self._last_match_center))
        if self._last_match_center == CONFIRM_CENTER:
            self.confirm_clicks += 1
            if self.confirm_clicks == self.success_on_confirm_attempt:
                self.dialog_visible = False
        elif self._last_match_center == CANCEL_CENTER:
            self.cancel_clicks += 1
            if self.cancel_succeeds:
                self.dialog_visible = False

    def wait(self, ms: int | float) -> None:
        self.elapsed_ms += int(ms)

    def save_debug_screenshot(self, prefix: str) -> str:
        self.screenshot_prefixes.append(prefix)
        return f"logs/{prefix}.png"

    def _log(self, message: str) -> None:
        self.logs.append(message)

    def _debug(self, message: str) -> None:
        return None


@pytest.mark.parametrize("success_attempt", [1, 2, 3])
def test_stall_purchase_succeeds_when_dialog_disappears(
    success_attempt: int,
) -> None:
    task = FakePurchaseTask(success_on_confirm_attempt=success_attempt)

    assert task.confirm_stall_purchase()

    confirm_clicks = [item for item in task.clicks if item[1] == CONFIRM_CENTER]
    assert len(confirm_clicks) == success_attempt
    assert task.cancel_clicks == 0
    assert task.screenshot_prefixes == []
    assert all(
        current[0] - previous[0] >= 3000
        for previous, current in zip(confirm_clicks, confirm_clicks[1:])
    )


def test_three_ineffective_confirmations_cancel_once_and_still_fail() -> None:
    task = FakePurchaseTask(success_on_confirm_attempt=None, cancel_succeeds=True)

    with pytest.raises(StallPurchaseConfirmationError, match="已取消本次购买"):
        task.confirm_stall_purchase()

    assert task.confirm_clicks == 3
    assert task.cancel_clicks == 1
    assert task.screenshot_prefixes == ["stall_purchase_confirm_stuck"]
    assert [time_ms for time_ms, center in task.clicks if center == CONFIRM_CENTER] == [
        0,
        3000,
        6000,
    ]


def test_cancel_failure_saves_second_screenshot_and_raises() -> None:
    task = FakePurchaseTask(success_on_confirm_attempt=None, cancel_succeeds=False)

    with pytest.raises(StallPurchaseCancelError, match="取消购买也未生效"):
        task.confirm_stall_purchase()

    assert task.confirm_clicks == 3
    assert task.cancel_clicks == 1
    assert task.screenshot_prefixes == [
        "stall_purchase_confirm_stuck",
        "stall_purchase_cancel_failed",
    ]


def test_missing_purchase_dialog_does_not_click_any_control() -> None:
    task = FakePurchaseTask(
        success_on_confirm_attempt=None,
        dialog_visible=False,
    )

    with pytest.raises(StallPurchaseConfirmationError, match="未确认购买弹窗"):
        task.confirm_stall_purchase()

    assert task.clicks == []
    assert task.screenshot_prefixes == ["stall_purchase_unconfirmed"]


class FakeRouteTask(BanquetAcquireMixin):
    BTN_BANQUET_GET_ITEM = "btn_banquet_get_item.png"
    ROI_BANQUET_ACTION = (960, 530, 210, 100)

    def __init__(self, outcomes: dict[str, bool], *, get_button_states: list[bool] | None = None) -> None:
        self.outcomes = outcomes
        self.get_button_states = list(get_button_states or [])
        self.descriptions: list[str] = []
        self.stall_confirmations = 0
        self.mall_confirmations = 0
        self.return_count = 0
        self.get_button_checks = 0
        self.get_button_clicks = 0
        self.logs: list[str] = []

    def ensure_route_panel_open(self) -> bool:
        return True

    def click_template_if_available(self, template, *, description: str, **kwargs) -> bool:
        self.descriptions.append(description)
        return self.outcomes.get(description, False)

    def confirm_stall_purchase(self, max_attempts: int = 3, retry_interval_ms: int = 3000) -> bool:
        self.stall_confirmations += 1
        return True

    def confirm_purchase_if_needed(self) -> bool:
        self.mall_confirmations += 1
        return True

    def return_to_banquet_panel(self, max_attempts: int = 4) -> bool:
        self.return_count += 1
        return True

    def wait_find_image_in_roi(self, template, roi, **kwargs) -> bool:
        assert template == self.BTN_BANQUET_GET_ITEM
        assert roi == self.ROI_BANQUET_ACTION
        assert kwargs["timeout_ms"] == self.PURCHASE_RESULT_CHECK_TIMEOUT_MS
        assert kwargs["threshold"] == 0.85
        self.get_button_checks += 1
        return self.get_button_states.pop(0) if self.get_button_states else False

    def click(self, offset: int = 3) -> None:
        self.get_button_clicks += 1

    def wait(self, ms: int | float) -> None:
        return None

    def _log(self, message: str) -> None:
        self.logs.append(message)


def test_local_stall_purchase_uses_strict_confirmation_once() -> None:
    task = FakeRouteTask(
        {
            "摆摊购买路径": True,
            "摆摊购买按钮": True,
        }
    )

    assert task.try_stall_route()

    assert task.stall_confirmations == 1
    assert task.return_count == 1
    assert "查看全服按钮" not in task.descriptions


def test_all_server_stall_purchase_uses_same_strict_confirmation() -> None:
    task = FakeRouteTask(
        {
            "摆摊购买路径": True,
            "摆摊购买按钮": False,
            "查看全服按钮": True,
            "全服摆摊购买按钮": True,
        }
    )

    assert task.try_stall_route()

    assert task.stall_confirmations == 1
    assert task.return_count == 1


def test_mall_purchase_keeps_existing_confirmation_path() -> None:
    task = FakeRouteTask(
        {
            "商城购买路径": True,
            "商城购买按钮": True,
            "商城购买确认按钮": True,
        }
    )

    assert task.try_mall_route()

    assert task.mall_confirmations == 1
    assert task.stall_confirmations == 0


def test_successful_mall_purchase_without_get_button_does_not_retry() -> None:
    task = FakeRouteTask(
        {
            "商城购买路径": True,
            "商城购买按钮": True,
            "商城购买确认按钮": True,
        },
        get_button_states=[False],
    )

    task.acquire_selected_item(2)

    assert task.mall_confirmations == 1
    assert task.get_button_checks == 1
    assert task.get_button_clicks == 0


@pytest.mark.parametrize(
    ("outcomes", "confirmation_attribute"),
    [
        (
            {
                "商城购买路径": True,
                "商城购买按钮": True,
                "商城购买确认按钮": True,
            },
            "mall_confirmations",
        ),
        (
            {
                "摆摊购买路径": True,
                "摆摊购买按钮": True,
            },
            "stall_confirmations",
        ),
        (
            {
                "摆摊购买路径": True,
                "摆摊购买按钮": False,
                "查看全服按钮": True,
                "全服摆摊购买按钮": True,
            },
            "stall_confirmations",
        ),
    ],
    ids=["mall", "local-stall", "all-server-stall"],
)
def test_purchase_retries_full_acquisition_once_when_get_button_remains(
    outcomes: dict[str, bool],
    confirmation_attribute: str,
) -> None:
    task = FakeRouteTask(outcomes, get_button_states=[True, False])

    task.acquire_selected_item(4)

    assert getattr(task, confirmation_attribute) == 2
    assert task.descriptions.count("推荐帮派仓库") == 2
    assert task.get_button_checks == 2
    assert task.get_button_clicks == 1
    assert any("判定购买异常，再次获取 1/1" in message for message in task.logs)


def test_second_purchase_failure_logs_and_stops_without_third_attempt() -> None:
    task = FakeRouteTask(
        {
            "商城购买路径": True,
            "商城购买按钮": True,
            "商城购买确认按钮": True,
        },
        get_button_states=[True, True],
    )

    task.acquire_selected_item(6)

    assert task.mall_confirmations == 2
    assert task.get_button_checks == 2
    assert task.get_button_clicks == 1
    assert any("再次获取后仍显示获取按钮" in message for message in task.logs)


def test_warehouse_success_does_not_run_purchase_result_check() -> None:
    task = FakeRouteTask(
        {
            "推荐帮派仓库": True,
            "帮派仓库提交按钮": True,
        },
        get_button_states=[True],
    )

    task.acquire_selected_item(8)

    assert task.get_button_checks == 0
    assert task.get_button_clicks == 0
    assert task.get_button_states == [True]


def test_pozhen_no_longer_selects_six_or_five_dish_tabs(monkeypatch) -> None:
    calls: list[str] = []
    task = object.__new__(PZSYTask)

    monkeypatch.setattr(
        BanquetAcquireMixin,
        "process_banquet_items",
        lambda self: calls.append("process-eight-slots"),
    )

    PZSYTask.process_banquet_items(task)

    assert calls == ["process-eight-slots"]
    assert not hasattr(PZSYTask, "select_submit_six_dishes")
    assert not hasattr(PZSYTask, "select_submit_five_dishes")
