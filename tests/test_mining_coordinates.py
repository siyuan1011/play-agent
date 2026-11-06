"""真实到点帧的 HUD 坐标回读回归。"""
from pathlib import Path
from unittest.mock import Mock
import cv2
import pytest
from ymjh_bot.task.SHRW_task import LifeUI, SHRWTask


@pytest.mark.parametrize("coordinate", [(850, 1488), (855, 1700), (906, 1524), (912, 1524), (1212, 1582), (856, 1488), (1485, 1741), (1488, 1744)])
def test_arrived_emerald_coordinate(coordinate):
    """参数：coordinate 为人工核对过的真实到点坐标。"""
    path = Path(__file__).parent / f"fixtures/ymjh/mining_coordinates/{coordinate[0]}_{coordinate[1]}.png"  # 原始失败帧。
    frame = cv2.imread(str(path))  # 到达祖母绿矿点后的截图。
    ui = LifeUI(SHRWTask())  # 无设备依赖的界面观察器。
    assert ui.current_coordinate(frame) == coordinate
    assert ui.at_coordinate(frame, coordinate)
    assert not ui.at_coordinate(frame, (1156, 1698))

@pytest.mark.parametrize("roi, expected", [((119,619,95,27),1218),((235,619,95,27),1582)])
def test_map_input_digit_eight_is_not_three(roi, expected):
    """参数：roi 为输入框区域；expected 为人工核对的坐标输入值。"""
    from ymjh_bot.task.SHRW_task import read_number
    frame = cv2.imread(str(Path(__file__).parent / 'fixtures/ymjh/mining_coordinates/field_1218_1582.png'))  # 输入字段正例。
    x, y, width, height = roi  # x/y 为像素起点；width/height 为裁剪尺寸。
    mask = cv2.inRange(frame[y:y+height,x:x+width],(190,190,190),(255,255,255))  # 生产白色阈值。
    assert read_number(mask) == expected


def test_bright_map_background_cannot_hide_coordinate_digits():
    """粘连背景不能被跳过后把 1488 静默读成 1。"""
    from ymjh_bot.task.SHRW_task import read_number
    frame = cv2.imread(str(Path(__file__).parent / 'fixtures/ymjh/mining_coordinates/856_1488.png'))  # 浅色地图粘连现场。
    region = frame[:21,1224:1280]  # 逗号之后的完整 Y 坐标字段。
    mask = cv2.inRange(region,(185,185,185),(255,255,255))  # 原始固定阈值分割。
    assert read_number(mask,hud=True) == 1
    assert LifeUI.read_hud_field(region,left_parenthesis=False) == 1488


def test_hud_short_six_is_not_five():
    """十一像素高的数字 6 仍须与 5 区分，不依赖到点容差掩盖读错。"""
    frame = cv2.imread(str(Path(__file__).parent / 'fixtures/ymjh/mining_coordinates/856_1488_short6.png'))  # 856 被误读为 855 的现场。
    assert LifeUI(SHRWTask()).current_coordinate(frame) == (856,1488)


@pytest.mark.parametrize("coordinate", [(1586, 1778), (856, 1488)])
def test_map_current_coordinate_uses_actual_location(coordinate):
    """参数：coordinate 为人工核对的地图当前坐标，不取上方前往输入框。"""
    frame = cv2.imread(str(Path(__file__).parent / f'fixtures/ymjh/mining_coordinates/map_{coordinate[0]}_{coordinate[1]}.png'))  # 地图真实帧。
    assert LifeUI(SHRWTask()).map_coordinate(frame) == coordinate


def test_hud_icon_obstruction_requires_map_fallback():
    """小地图图标遮住数字时拒绝猜值；主界面不能当作地图回读。"""
    frame = cv2.imread(str(Path(__file__).parent / 'fixtures/ymjh/mining_coordinates/hud_obstructed_1586_1778.png'))  # 实际已到黄铜点但 HUD 遮挡的失败帧。
    ui = LifeUI(SHRWTask())  # 不连接设备的真实观察器。
    assert ui.current_coordinate(frame) is None
    assert ui.map_coordinate(frame) is None


@pytest.mark.parametrize("readings, expected", [([(1586,1778)] * 3, True), ([(1586,1778), None], False), ([(1586,1778), (1550,1778)], False)])
def test_map_arrival_requires_three_confirmations_and_closes_map(readings, expected):
    """参数：readings 为连续地图回读；expected 为是否允许确认到点。"""
    task = Mock()  # 无设备的导航接口，主界面已恢复。
    task.is_main_scene.return_value = True
    task.is_stopped.return_value = False
    ui = LifeUI(task)  # 被测备用到点路径。
    ui.screenshot = Mock()
    ui.map_coordinate = Mock(side_effect=readings)
    assert ui.confirm_arrival_on_map((1586,1778)) == expected
    task.ensure_local_map_open.assert_called_once()
    task.close_map_after_navigation.assert_called_once()
    assert ui.map_coordinate.call_count == len(readings)


@pytest.mark.parametrize("name, fallback", [("hud_obstructed_1586_1778", True), ("850_1488", False)])
def test_arrival_fallback_is_only_for_unreadable_hud(name, fallback):
    """参数：name 为实际 HUD 帧；fallback 表示是否应该使用地图备用确认。"""
    from botCore import VisionEngine
    frame = cv2.imread(str(Path(__file__).parent / f'fixtures/ymjh/mining_coordinates/{name}.png'))  # 不可读到点帧或可读错误坐标。
    task = SHRWTask()  # 保留真实坐标和场景识别，替换时间与设备。
    task._vision = VisionEngine()
    task._make_deadline = Mock(return_value=1)
    task._is_deadline_expired = Mock(side_effect=[False, True])
    task.wait = Mock()
    task._log = Mock()
    ui = LifeUI(task)  # 被测到点流程。
    ui.screenshot = Mock(return_value=frame)
    ui.confirm_arrival_on_map = Mock(return_value=True)
    if fallback:
        ui.wait_arrival((1586,1778))
        ui.confirm_arrival_on_map.assert_called_once_with((1586,1778))
    else:
        with pytest.raises(RuntimeError, match="未确认到达"):
            ui.wait_arrival((1586,1778))
        ui.confirm_arrival_on_map.assert_not_called()

@pytest.mark.parametrize('reading', [None, (1580, 1778)])
def test_action_confirms_arrival_despite_unreadable_or_inaccurate_hud(reading):
    """参数：reading 为遮挡或偏差的 HUD 回读，采集入口可独立确认到点。"""
    from botCore import VisionEngine
    task = SHRWTask()  # 使用真实入口识别的任务。
    task._vision = VisionEngine()
    task.wait = Mock()
    task._is_deadline_expired = Mock(return_value=False)
    frame = cv2.imread(str(Path(__file__).parent / 'fixtures/ymjh/mining_coordinates/hud_obstructed_1586_1778.png'))  # 有可执行采集标志的到点现场。
    ui = LifeUI(task)  # 只隔离设备和 HUD 读数。
    ui.screenshot = Mock(return_value=frame)
    ui.current_coordinate = Mock(return_value=reading)
    ui.confirm_arrival_on_map = Mock()
    ui.wait_arrival((1586, 1778))
    assert task.wait.call_count == 2
    ui.confirm_arrival_on_map.assert_not_called()


def test_action_during_pathfinding_cannot_confirm_arrival():
    """途中经过矿点的按钮不能让寻路提前完成。"""
    task = Mock()  # 模拟仍在寻路的主场景。
    task.is_stopped.return_value = False
    task.is_main_scene.return_value = True
    task.find_configured_gather_action.return_value = (935, 466)
    task._vision.match_template.return_value.found = True
    task._remaining_ms.return_value = 1000
    task.wait_auto_pathfinding.return_value = False
    task._is_deadline_expired.side_effect = [False, False, False, True]
    ui = LifeUI(task)  # 仅隔离截图，不绕过生产到点判定。
    ui.screenshot = Mock()
    ui.confirm_arrival_on_map = Mock()
    with pytest.raises(RuntimeError, match='后续寻路'):
        ui.wait_arrival((1586, 1778))
    ui.confirm_arrival_on_map.assert_not_called()


def test_arrival_waits_for_resumed_pathfinding_after_transfer():
    """传送间隙后继续寻路，须再次等待结束再连续确认采集入口。"""
    task = Mock()  # 主场景先重新寻路，随后连续三帧可采集。
    task.is_stopped.return_value = False
    task._is_deadline_expired.return_value = False
    task._remaining_ms.return_value = 1000
    task.is_main_scene.return_value = True
    task.is_scene_transition_loading.return_value = False
    task.find_configured_gather_action.return_value = (935, 466)
    task._vision.match_template.side_effect = [Mock(found=True)] + [Mock(found=False)] * 3
    task.wait_auto_pathfinding.return_value = True
    ui = LifeUI(task)  # 只隔离截图来源，不改变到点状态机。
    ui.screenshot = Mock()
    ui.wait_arrival((1121, 1626))
    task.wait_auto_pathfinding.assert_called_once_with(timeout_ms=1000, missing_threshold=3)
    assert task.find_configured_gather_action.call_count == 3
