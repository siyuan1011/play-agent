"""体力不足入口必须结束采集，不能当作空矿点继续换线。"""
from pathlib import Path
from unittest.mock import Mock

import cv2
import pytest

from botCore import VisionEngine
from ymjh_bot.task.SHRW_task import LifeFlow, LifeSignal, LifeTaskUnavailable, LifeUI, SHRWTask


@pytest.mark.parametrize('name, insufficient', [
    ('stamina_insufficient_action', True),
    ('emerald_action_1481_1744', False),
    ('silver_action_1212_1586', False),
    ('mining_hand_action', False),
    ('empty_slope', False),
    ('empty_906', False),
    ('gathering_border_right', False),
    ('gather_success_gold', False),
])
def test_stamina_action_real_frames(name, insufficient):
    """参数：name 为真实帧名称；insufficient 表示是否确有红色体力不足标记。"""
    task = SHRWTask()  # 使用实际识图逻辑，无设备操作。
    task._vision = VisionEngine()
    frame = cv2.imread(str(Path(__file__).parent / f'fixtures/ymjh/mining_coordinates/{name}.png'))  # 正反例现场。
    task.screenshot = Mock(return_value=frame)
    assert (LifeUI(task).observe().signal == LifeSignal.NO_STAMINA) == insufficient


def test_insufficient_stamina_stops_before_empty_point_or_line_switch():
    """真实耗尽入口经生产循环转成明确停止原因，不返回空矿点或继续换线。"""
    task = SHRWTask({'strategy': 'continuous', 'material': 'tungsten_ore'})  # 持续采集的原失败场景。
    task._vision = VisionEngine()
    task._log = Mock()
    task.click_point = Mock()
    task.screenshot = Mock(return_value=cv2.imread(str(Path(__file__).parent / 'fixtures/ymjh/mining_coordinates/stamina_insufficient_action.png')))
    ui = LifeUI(task)  # 保留真实入口观察，只隔离地图和线路操作。
    ui.travel_to_target_map = Mock()
    ui.move_to = Mock()
    flow = LifeFlow(task, ui)  # 执行实际采集流程。
    flow.switch_line = Mock()
    with pytest.raises(LifeTaskUnavailable, match='体力不足'):
        flow.run(((855, 1700), (846, 1696)))
    flow.switch_line.assert_called_once()  # 仅初始化线路，不能再换线寻找资源。
    ui.move_to.assert_called_once_with((855, 1700))
    task.click_point.assert_not_called()
    assert task._successful_gathers == 0
    assert all('未找到采集物' not in call.args[0] for call in task._log.call_args_list)  # call 为各条流程日志调用。
