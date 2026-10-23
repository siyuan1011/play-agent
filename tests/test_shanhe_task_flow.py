"""山河器免费搜索的真实帧、流程及配置回归。"""
from pathlib import Path
from unittest.mock import Mock

import cv2
import pytest

from botCore import StepStopException, VisionEngine
from ymjh_bot.task.RCGM_task import RCGMTask
from ymjh_bot.runner.task_factory import create_task_instances
from ymjh_bot.ui.task_queue_state import normalize_rcgm_settings
from ymjh_bot.ym_game_task import YmGameTask

FIXTURES = Path(__file__).parent / 'fixtures' / 'daily_purchase'  # 用户提供的真实流程帧目录。

@pytest.mark.parametrize('name,roi,positive', [
    ('system_menu', RCGMTask.ROI_SYSTEM_MENU, 1),
    ('numeric_system', RCGMTask.ROI_NUMERIC_SYSTEM, 2),
    ('shanhe_entry', RCGMTask.ROI_SHANHE_ENTRY, 3),
    ('shanhe_title', RCGMTask.ROI_SHANHE_TITLE, 4),
    ('shanhe_search_tab', RCGMTask.ROI_SHANHE_SEARCH_TAB, 4),
    ('shanhe_free', RCGMTask.ROI_SHANHE_FREE, 4),
])
def test_real_markers(name, roi, positive):
    """name 为模板名，roi 为像素识别区域，positive 为正例帧编号。"""
    task = RCGMTask()  # 使用正式模板配置的视觉测试实例。
    task.setup(Mock(), VisionEngine())
    frame = cv2.imread(str(FIXTURES / f'shanhe_ex{positive}.png'))  # 标记可见的完整真实截图。
    assert task._find(name, roi, screenshot=frame)
    negative = cv2.imread(str(FIXTURES / ('shanhe_ex4.png' if positive < 4 else 'shanhe_ex1.png')))  # 来自不同页面的真实反例。
    assert not task._find(name, roi, screenshot=negative)

@pytest.mark.parametrize('free_available', [True, False])
def test_search_clicks_only_when_free_and_exits(monkeypatch, free_available):
    """monkeypatch 隔离设备依赖；free_available 为免费按钮是否存在。"""
    task = RCGMTask({'shanhe': True})  # 只执行免费搜索的当前角色实例。
    monkeypatch.setattr(task, '_find', Mock(return_value=False))
    monkeypatch.setattr(task, '_click_marker', Mock())
    monkeypatch.setattr(task, '_require_marker', Mock())
    monkeypatch.setattr(task, 'wait_find_image_in_roi', Mock(return_value=free_available))
    monkeypatch.setattr(task, 'click', Mock())
    monkeypatch.setattr(task, 'wait', Mock())
    monkeypatch.setattr(task, '_close_shanhe_panel', Mock(return_value=True))
    assert task.purchase_selected_goods()  # 只勾选山河器时不能进入商城。
    task._find.assert_not_called()
    assert task.search_shanhe()
    assert [call.args[0] for call in task._click_marker.call_args_list] == [  # call 为每个导航点击的调用记录。
        'system_menu', 'numeric_system', 'shanhe_entry',
    ]
    assert task.click.call_count == int(free_available)
    task._close_shanhe_panel.assert_called_once()
    if free_available:
        assert task.search_shanhe()  # 同一任务重试时只能退出，不能再次免费搜索。
        task.click.assert_called_once_with(offset=0)

def test_disabled_and_stopped_do_not_click(monkeypatch):
    """monkeypatch 隔离设备点击；未勾选和用户停止均不能点击。"""
    task = RCGMTask()  # 默认未勾选任何日常任务的实例。
    monkeypatch.setattr(task, '_find', Mock())
    assert task.search_shanhe()
    task._find.assert_not_called()
    task._stop_requested = True  # 用户已请求停止。
    with pytest.raises(StepStopException):
        task.search_shanhe()
    task._find.assert_not_called()

def test_unconfirmed_page_never_searches(monkeypatch):
    """monkeypatch 隔离设备；页面未确认时不得按按钮缺失处理为成功。"""
    task = RCGMTask({'shanhe': True})  # 山河器导航尚未确认的实例。
    monkeypatch.setattr(task, '_find', Mock(return_value=True))
    monkeypatch.setattr(task, '_require_marker', Mock(side_effect=RuntimeError('页面未确认')))
    monkeypatch.setattr(task, 'click', Mock())
    with pytest.raises(RuntimeError, match='页面未确认'):
        task.search_shanhe()
    task.click.assert_not_called()

def test_old_settings_and_role_isolation():
    """旧配置缺少山河器时保持关闭；每个角色获得独立的点击状态。"""
    old = normalize_rcgm_settings({'silver_box': True})  # 升级前只有购买选项的配置。
    assert old['silver_box'] and not old['shanhe']
    first, second = create_task_instances(  # first、second 为模拟两个角色分别创建的任务实例。
        [{'key': 'RCGM', 'class': RCGMTask}] * 2, {'RCGM': {'shanhe': True}},
    )
    first._shanhe_search_clicked = True
    assert second.rcgm_settings['shanhe']
    assert not second._shanhe_search_clicked
    assert second.task_name == '日常任务'

def test_paid_button_is_not_free():
    """同一真实帧中的雇佣十连不得匹配为免费搜索。"""
    task = RCGMTask()  # 使用正式免费搜索模板的测试实例。
    task.setup(Mock(), VisionEngine())
    frame = cv2.imread(str(FIXTURES / 'shanhe_ex4.png'))  # 同时含免费搜索与雇佣十连的真实页面。
    assert not task._find('shanhe_free', (995, 640, 150, 50), screenshot=frame)

@pytest.mark.parametrize('frame_name,marker,roi', [
    ('shanhe_animation', 'shanhe_animation', RCGMTask.ROI_SHANHE_CONTINUE),
    ('shanhe_result', 'shanhe_result', RCGMTask.ROI_SHANHE_CONTINUE),
    ('shanhe_compass', 'shanhe_compass_close', RCGMTask.ROI_SHANHE_COMPASS_CLOSE),
])
def test_real_exit_markers(frame_name, marker, roi):
    """frame_name 为实机帧名，marker 为退出标记，roi 为像素识别区域。"""
    task = RCGMTask()  # 实际模板匹配实例。
    task.setup(Mock(), VisionEngine())
    frame = cv2.imread(str(FIXTURES / f'{frame_name}.png'))  # 对应的实机动画或弹层画面。
    assert task._find(marker, roi, screenshot=frame)
    normal = cv2.imread(str(FIXTURES / 'shanhe_ex4.png'))  # 未打开弹层的正常山河器页面。
    assert not task._find(marker, roi, screenshot=normal)

def test_shanhe_closed_before_generic_startup(monkeypatch):
    """monkeypatch 隔离设备；山河器须在通用省电唤醒前关闭。"""
    task = RCGMTask({'shanhe': True})  # 从山河器页面启动的实例。
    order = []  # 记录安全关闭与通用启动的实际执行顺序。
    monkeypatch.setattr(task, '_find', Mock(return_value=True))
    monkeypatch.setattr(task, '_close_shanhe_panel', lambda: order.append('close'))
    monkeypatch.setattr(YmGameTask, 'before_start', lambda self: order.append('startup'))  # self 为当前任务实例。
    task.before_start()
    assert order == ['close', 'startup']

def test_compass_closed_once_then_main_verified(monkeypatch):
    """monkeypatch 隔离设备；退出罗盘只能点击关闭标记，并验证返回主界面。"""
    task = RCGMTask({'shanhe': True})  # 等待退出罗盘的任务实例。
    monkeypatch.setattr(task, '_find', Mock(side_effect=[True, False, False, True]))
    monkeypatch.setattr(task, 'click', Mock())
    monkeypatch.setattr(task, 'wait', Mock())
    assert task._close_shanhe_panel()
    task.click.assert_called_once_with(offset=0)
