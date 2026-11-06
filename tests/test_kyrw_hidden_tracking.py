"""课业隐藏追踪与吟风前缀的生产故障回归。"""

from pathlib import Path
from unittest.mock import Mock

import cv2
import pytest

from botCore import StepStopException, VisionEngine
from ymjh_bot.task.KYRW_task import KYRWTask
from ymjh_bot.ym_game_task import TaskSidebarStateError


FIXTURES = Path(__file__).parent / "fixtures/ymjh/kyrw_hidden_20261028"  # 设备现场截图目录。


@pytest.mark.parametrize("name, expected", [("restored_sidebar", True), ("sidebar_top", False)])
def test_yinfeng_sidebar(name, expected):
    """参数：name 为现场帧名；expected 为是否应识别到吟风课业。"""
    frame = cv2.imread(str(FIXTURES / f"{name}.png"))  # 当前回归帧。
    result = VisionEngine().match_template(  # 实际侧栏模板组匹配结果。
        frame, KYRWTask.KEYE_SIDEBAR_TEMPLATES, threshold=0.85, roi=(40, 135, 330, 430)
    )
    assert result.found is expected


@pytest.mark.parametrize("name", ["full_jianghu", "hidden_keye", "shown_keye"])
def test_full_list_selected_and_unselected(name):
    """参数：name 为课业条目选中或未选中的现场帧名。"""
    frame = cv2.imread(str(FIXTURES / f"{name}.png"))  # 完整任务列表帧。
    result = VisionEngine().match_template(  # 课业条目前缀的匹配结果。
        frame, KYRWTask.FULL_KEYE_PREFIX, threshold=0.9, roi=(135, 220, 240, 395)
    )
    assert result.found


@pytest.mark.parametrize("name, checked", [("hidden_keye", False), ("shown_keye", True)])
def test_tracking_checkbox_states(name, checked):
    """参数：name 为现场帧名；checked 为实际勾选状态。"""
    frame = cv2.imread(str(FIXTURES / f"{name}.png"))  # 含追踪复选框的现场帧。
    for template, expected in ((KYRWTask.TRACK_CHECKED, checked), (KYRWTask.TRACK_UNCHECKED, not checked)):
        # template 为复选框模板；expected 为该模板是否应命中。
        result = VisionEngine().match_template(  # 两种状态必须互斥，不能误切换已勾选状态。
            frame, template, threshold=0.95, roi=(650, 550, 210, 60)
        )
        assert result.found is expected


def test_existing_keye_missing_does_not_complete():
    """NPC 已确认课业时，连续缺失必须失败，防止跳回接取循环。"""
    task = KYRWTask()  # 无设备的流程测试实例。
    task._existing_keye_expected = True
    task.wait_auto_pathfinding = Mock(return_value=True)
    task._handle_keye_flow_state_once = Mock(return_value=task.KEYE_FLOW_STATE_IDLE)
    task.click_keye_task_from_sidebar = Mock(return_value=False)
    task.wait = Mock()
    with pytest.raises(RuntimeError, match="停止重复接取"):
        task.run_keye_flow()


def test_restore_missing_panel_and_stop_propagate():
    """面板无法确认和用户停止均不得转成恢复成功。"""
    task = KYRWTask()  # 独立恢复测试实例。
    task.ensure_left_task_sidebar_visible = Mock(side_effect=StepStopException())
    with pytest.raises(StepStopException):
        task.restore_hidden_keye_tracking()
    task.ensure_left_task_sidebar_visible = Mock()
    task.click_point = Mock()
    task.wait = Mock()
    task.screenshot = Mock()
    task._match_task_fullscreen_panel = Mock(return_value=Mock(found=False))
    with pytest.raises(RuntimeError, match="未确认完整任务面板"):
        task.restore_hidden_keye_tracking()


def test_startup_resets_existing_task_expectation():
    """完整任务重试不能继承上一轮的 NPC 确认状态。"""
    task = KYRWTask()  # 待模拟重试的课业实例。
    task._existing_keye_expected = True
    task.reset_startup_state()
    assert not task._existing_keye_expected


@pytest.mark.parametrize("unchecked", [False, True])
def test_restore_only_checks_unchecked_tracking(unchecked):
    """参数：unchecked 表示课业追踪是否未勾选；已勾选时禁止再次切换。"""
    task = KYRWTask()  # 模拟完整列表的恢复实例。
    task.ensure_left_task_sidebar_visible = Mock()
    task.click_point = Mock()
    task.click = Mock()
    task.wait = Mock()
    task.screenshot = Mock()
    task._match_task_fullscreen_panel = Mock(return_value=Mock(found=True))
    task.find_image_once = Mock(side_effect=[False, False, unchecked])
    task._vision = Mock()
    task._vision.match_template.return_value = Mock(found=True, center=(222, 429))
    task.wait_image_appear = Mock(return_value=True)
    task.close_all_panels = Mock()
    task.find_keye_task_in_sidebar = Mock(return_value=True)
    task.restore_hidden_keye_tracking()
    checkbox_calls = [  # 所有点击中针对复选框的调用。
        call for call in task.click_point.call_args_list  # call 为一次点击调用记录。
        if call.args == task.POINT_TRACK_CHECKBOX
    ]
    assert len(checkbox_calls) == int(unchecked)
    task.find_keye_task_in_sidebar.assert_called_once()


@pytest.mark.parametrize("loading", [False, True])
def test_sidebar_error_only_retries_when_loading(loading):
    """参数：loading 为失败时是否已进入过图；普通侧栏错误必须继续传播。"""
    task = KYRWTask()  # 模拟跨图时序的课业实例。
    task._is_deadline_expired = Mock(return_value=False)
    task.wait_auto_pathfinding = Mock(side_effect=[True, StepStopException()])
    task._handle_keye_flow_state_once = Mock(return_value=task.KEYE_FLOW_STATE_IDLE)
    task.click_keye_task_from_sidebar = Mock(side_effect=TaskSidebarStateError("侧栏失效"))
    task.find_image_once = Mock(return_value=loading)
    with pytest.raises(StepStopException if loading else TaskSidebarStateError):
        task.run_keye_flow()


def test_flow_handles_returned_card_panel():
    """NPC 再次打开选卡面板后应接续选卡，不能扫描被遮挡的侧栏。"""
    task = KYRWTask()  # 模拟新一轮选卡的课业实例。
    task.close_keye_completion_dialog_if_visible = Mock(return_value=False)
    task.cancel_refresh_confirm_if_visible = Mock(return_value=False)
    task.find_image_once = Mock(return_value=True)
    task.try_select_default_keye_card = Mock(return_value=True)
    assert task._handle_keye_flow_state_once() == task.KEYE_FLOW_STATE_HANDLED
    task.try_select_default_keye_card.assert_called_once()


def test_sidebar_scan_rechecks_new_dialog():
    """扫描期间进入剧情时处理新状态，下一轮仍响应停止。"""
    task = KYRWTask()  # 模拟先空闲、后出现对话的时序。
    task._is_deadline_expired = Mock(return_value=False)
    task.wait_auto_pathfinding = Mock(side_effect=[True, StepStopException()])
    task._handle_keye_flow_state_once = Mock(side_effect=[task.KEYE_FLOW_STATE_IDLE, task.KEYE_FLOW_STATE_HANDLED])
    task.click_keye_task_from_sidebar = Mock(side_effect=TaskSidebarStateError("剧情进入"))
    task.find_image_once = Mock(return_value=False)
    with pytest.raises(StepStopException):
        task.run_keye_flow()
    assert task._handle_keye_flow_state_once.call_count == 2
