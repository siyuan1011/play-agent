"""帮派最后一环提交后短暂检查后续任务并跳回接取步骤的回归。"""

from pathlib import Path
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

from botCore import StepJumpException, StepStopException, VisionEngine
from botCore.execution import DslStepExecutor, resolve_step_jump
from ymjh_bot.task.BPRW_task import BPRWTask


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "bprw" / "npc_accept_confirm.png"  # 用户提供的 2026-10-14 18:03:32 真实帧，包含确定及箭头，不含接取按钮。


@pytest.fixture
def task() -> BPRWTask:
    """创建不操作设备的帮派任务，保留提交和步骤跳转的真实逻辑。"""
    instance = BPRWTask()  # 本用例独立的任务实例。
    instance.setup(Mock(), VisionEngine())
    instance.wait = Mock()
    instance.click_template_if_available = Mock(return_value=True)
    instance.confirm_submit_if_needed = Mock(return_value=True)
    instance.wait_auto_pathfinding = Mock(return_value=True)
    instance.wait_image_appear = Mock(return_value=False)
    instance.drain_dialog_next = Mock(return_value=0)
    instance.save_debug_screenshot = Mock(return_value="bprw_failure.png")
    return instance


def test_submission_finds_next_task_and_jumps_without_clicking_arrow(task: BPRWTask) -> None:
    """参数：task：模拟任务；命中后续接取按钮立即跳转，避免继续点击剧情箭头。"""
    task.wait_image_appear.return_value = True
    task._warehouse_item_checked = True
    with pytest.raises(StepJumpException) as raised:  # raised 为提交分支向 DSL 执行器发出的步骤跳转。
        task.handle_submit_panel_if_visible()
    assert raised.value.target == "accept_task"
    assert task._warehouse_item_checked is False
    task.wait_auto_pathfinding.assert_called_once_with(timeout_ms=120000)
    task.wait_image_appear.assert_called_once_with(task.BTN_BANGPAI_TASK_ACCEPT, timeout_ms=3000)
    task.drain_dialog_next.assert_not_called()


def test_submission_without_next_task_preserves_normal_flow(task: BPRWTask) -> None:
    """参数：task：模拟任务；三秒内未发现后续接取入口时继续原有剧情流程。"""
    task._warehouse_item_checked = True
    assert task.handle_submit_panel_if_visible() is True
    task.confirm_submit_if_needed.assert_called_once()
    task.wait_auto_pathfinding.assert_called_once_with(timeout_ms=120000)
    task.wait_image_appear.assert_called_once_with(task.BTN_BANGPAI_TASK_ACCEPT, timeout_ms=3000)
    task.drain_dialog_next.assert_called_once()
    assert task._warehouse_item_checked is True


def test_unrelated_screen_does_not_wait_for_accept(task: BPRWTask) -> None:
    """参数：task：模拟任务；没有提交面板时不增加接取检测和等待。"""
    task.click_template_if_available.return_value = False
    assert task.handle_submit_panel_if_visible() is False
    task.confirm_submit_if_needed.assert_not_called()
    task.wait_auto_pathfinding.assert_not_called()
    task.wait_image_appear.assert_not_called()
    task.drain_dialog_next.assert_not_called()


def test_transition_timeout_does_not_check_accept_or_click_arrow(task: BPRWTask) -> None:
    """参数：task：模拟任务；寻路过图未结束时保留失败截图，不误判没有后续。"""
    task.wait_auto_pathfinding.return_value = False
    with pytest.raises(RuntimeError, match="等待自动寻路或过图结束超时"):
        task.handle_submit_panel_if_visible()
    task.save_debug_screenshot.assert_called_once_with("bangpai_task_transition_timeout")
    task.wait_image_appear.assert_not_called()
    task.drain_dialog_next.assert_not_called()


def test_normal_transition_still_advances_dialog(task: BPRWTask) -> None:
    """参数：task：模拟任务；提交以外的调用沿用原有寻路后剧情推进行为。"""
    task.wait_bangpai_task_transition("点击侧栏任务后")
    task.drain_dialog_next.assert_called_once()


def test_wait_happens_after_pathfinding_before_dialog(task: BPRWTask) -> None:
    """参数：task：模拟任务；固定提交、寻路、短暂识别、普通对话的执行顺序。"""
    calls = Mock()  # 记录各业务动作实际发生顺序的父替身。
    calls.attach_mock(task.confirm_submit_if_needed, "confirm_submit")
    calls.attach_mock(task.wait_auto_pathfinding, "pathfinding")
    calls.attach_mock(task.wait_image_appear, "find_accept")
    calls.attach_mock(task.drain_dialog_next, "dialog")
    task.handle_submit_panel_if_visible()
    assert [call[0] for call in calls.mock_calls] == [  # call 为按执行顺序记录的一次动作调用。
        "confirm_submit", "pathfinding", "find_accept", "dialog",
    ]


def test_real_confirmation_is_not_misread_as_accept(task: BPRWTask) -> None:
    """参数：task：模拟任务；真实帧中的确定和箭头不应冒充帮派任务接取按钮。"""
    frame = cv2.imread(str(FIXTURE_PATH))  # 用户提供的完整 NPC 确认对话真实帧。
    assert frame is not None
    assert task._vision.match_template(frame, task.BTN_OK).found
    assert task._vision.match_template(frame, task.BTN_DIALOG_NEXT).found
    assert not task._vision.match_template(frame, task.BTN_BANGPAI_TASK_ACCEPT).found


def test_wait_appear_polls_new_frames_for_delayed_accept(task: BPRWTask) -> None:
    """参数：task：模拟任务；复用真实等待接口，从过渡帧轮询到接取按钮出现。"""
    blank = np.zeros((720, 1280, 3), dtype=np.uint8)  # 自动寻路刚结束时尚无按钮的合成过渡帧。
    ready = blank.copy()  # 后续出现接取按钮的合成画面。
    button = cv2.imread(task.BTN_BANGPAI_TASK_ACCEPT)  # 生产使用的接取按钮模板图块。
    assert button is not None
    ready[433:433 + button.shape[0], 939:939 + button.shape[1]] = button
    task.screenshot = Mock(side_effect=[blank, ready])
    task.wait_image_appear = BPRWTask.wait_image_appear.__get__(task)
    with pytest.raises(StepJumpException):
        task.handle_submit_panel_if_visible()
    assert task.screenshot.call_count == 2
    task.drain_dialog_next.assert_not_called()


def test_step_executor_preserves_jump_back_to_accept(task: BPRWTask) -> None:
    """参数：task：模拟任务；主流程中提交发出的跳转应由公共执行器交回接取步骤。"""
    task.close_completion_dialog_if_visible = Mock(return_value=False)
    task.handle_bangpai_flow_once = task.handle_submit_panel_if_visible
    task.wait_image_appear.return_value = True
    executor = DslStepExecutor(should_stop=lambda: False, emit=Mock())  # 单任务和队列共用的真实步骤执行器。
    result = executor.execute(task, "run_task_flow", BPRWTask.run_task_flow, BPRWTask.run_task_flow._step_meta)  # 主流程遇到接取入口时产生的执行结果。
    assert result.success
    assert task._jump_target == "accept_task"
    steps = task.get_steps()  # DSL 按源码顺序发现的任务步骤列表。
    current_index = next(index for index, record in enumerate(steps) if record[0] == "run_task_flow")  # index 为零起始步骤位置，record 为当前步骤定义。
    resolution = resolve_step_jump(task._jump_target, steps, current_index)  # runner 对接取跳转的实际解析结果。
    assert steps[resolution.next_index][0] == "accept_task"
    assert steps[resolution.next_index + 1][0] == "run_task_flow"
    assert not resolution.end_loop


def test_stop_during_short_wait_propagates(task: BPRWTask) -> None:
    """参数：task：模拟任务；短暂找图期间的用户停止异常不能被吞掉或转成继续剧情。"""
    task.wait_image_appear.side_effect = StepStopException("用户停止")
    with pytest.raises(StepStopException):
        task.handle_submit_panel_if_visible()
    task.drain_dialog_next.assert_not_called()


def test_tracker_fallback_remains_available(task: BPRWTask) -> None:
    """参数：task：模拟任务；保留原有侧栏消失后的活动页补接路径和状态更新。"""
    task.open_bangpai_activity = Mock()
    task.accept_task = Mock()
    task._warehouse_item_checked = True
    assert task.continue_after_tracker_disappeared() is True
    task.accept_task.assert_called_once()
    assert task._tracker_boundary_reaccepts == 1
    assert task._warehouse_item_checked is False
