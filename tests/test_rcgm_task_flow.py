"""日常购买真实反馈帧与未决扣款状态回归。"""

from pathlib import Path
from unittest.mock import Mock

import cv2
import pytest

from botCore import StepStopException, VisionEngine
from ymjh_bot.task.RCGM_task import RCGMTask


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "daily_purchase"  # 来自真机的完整反馈帧目录。


@pytest.mark.parametrize(
    ("frame_name", "expected"),
    [("temporary_bag_full", True), ("silver_success", False), ("no_feedback", False)],
)
def test_temporary_bag_rejection_template(frame_name: str, expected: bool) -> None:
    """frame_name 为真实帧名称；expected 为是否应识别到临时包裹拒绝提示。"""
    task = RCGMTask()  # 使用正式任务配置的模板、ROI 和阈值。
    task.setup(Mock(), VisionEngine())
    image = cv2.imread(str(FIXTURE_DIR / f"{frame_name}.png"))  # 用于验证正例、成功提示及无反馈反例的原始帧。
    assert image is not None
    assert task._find("temporary_bag_full", task.ROI_TOAST, screenshot=image) is expected


def make_purchase_task(frame_name: str, monkeypatch: pytest.MonkeyPatch) -> RCGMTask:
    """frame_name 为反馈帧名称；monkeypatch 为隔离真机点击及时间的测试补丁。"""
    task = RCGMTask({"silver_box": True})  # 正在购买银票礼盒的独立任务实例。
    task.setup(Mock(), VisionEngine())
    image = cv2.imread(str(FIXTURE_DIR / f"{frame_name}.png"))  # 本次购买后反复读取的真实反馈帧。
    monkeypatch.setattr(task, "screenshot", Mock(return_value=image))
    monkeypatch.setattr(task, "_require_marker", Mock())
    monkeypatch.setattr(task, "_quota_exhausted", Mock(return_value=False))
    monkeypatch.setattr(task, "_enter_quantity_99", Mock())
    monkeypatch.setattr(task, "wait", Mock())
    monkeypatch.setattr(task, "save_debug_screenshot", Mock(return_value="failure.png"))
    return task


def test_explicit_rejection_clears_pending_and_keeps_item_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    """monkeypatch 为依赖替身；明确拒绝应报可操作原因，并允许清理包裹后重试。"""
    task = make_purchase_task("temporary_bag_full", monkeypatch)  # 将收到游戏明确拒绝的购买任务。
    with pytest.raises(RuntimeError, match="购买被游戏拒绝：请先清理临时包裹"):
        task._purchase_item("silver_box", mall=True)
    assert task._pending_item is None
    assert task._completed_items == set()
    task._adb.tap.assert_called_once_with(*task.POINT_MALL_BUY)
    task.save_debug_screenshot.assert_called_once()
    # 使用同一实例模拟包裹清理后的重试，必须能够确认成功。
    task.screenshot.return_value = cv2.imread(str(FIXTURE_DIR / "silver_success.png"))
    task._purchase_item("silver_box", mall=True)
    assert task._pending_item is None
    assert task._completed_items == {"silver_box"}


def test_unknown_result_retains_pending_and_blocks_repurchase(monkeypatch: pytest.MonkeyPatch) -> None:
    """monkeypatch 为依赖替身；无明确反馈时仍保留防重复扣款保护。"""
    task = make_purchase_task("no_feedback", monkeypatch)  # 购买后没有成功或拒绝提示的任务。
    ticks = iter([0.0, 0.0, 6.0])  # 截止时间、首次轮询和超时轮询的单调秒数。
    monkeypatch.setattr("ymjh_bot.task.RCGM_task.time.monotonic", lambda: next(ticks))
    with pytest.raises(RuntimeError, match="未确认购买成功；保留未决状态"):
        task._purchase_item("silver_box", mall=True)
    assert task._pending_item == "silver_box"
    assert task._completed_items == set()
    with pytest.raises(RuntimeError, match="上次购买结果不明，禁止重复购买"):
        task.purchase_selected_goods()
    task._adb.tap.assert_called_once_with(*task.POINT_MALL_BUY)


def test_stop_during_result_poll_keeps_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    """monkeypatch 为依赖替身；购买后用户停止必须传播，不能改成明确拒绝或成功。"""
    task = make_purchase_task("no_feedback", monkeypatch)  # 点击购买后立即收到停止请求的任务。
    task.screenshot.side_effect = [task.screenshot.return_value, StepStopException("用户停止")]
    with pytest.raises(StepStopException):
        task._purchase_item("silver_box", mall=True)
    assert task._pending_item == "silver_box"
    assert task._completed_items == set()
