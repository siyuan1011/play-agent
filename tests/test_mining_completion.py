"""通过采集动作开始和结束确认完成，按钮消失不等于结束。"""
from unittest.mock import Mock
from pathlib import Path
import cv2
import pytest
from botCore import VisionEngine, StepStopException
from ymjh_bot.task.SHRW_task import LifeFlow, LifeObservation, LifeSignal, LifeUI, SHRWTask






def test_rain_acceleration_frame_and_click_edge():
    """雨天背景仍识别加速，同一持续标志仅点击一次。"""
    task = SHRWTask()  # 不连接设备的任务实例。
    task._vision = VisionEngine()
    task.click_point = Mock()
    ui = LifeUI(task)  # 使用原始失败帧的观察器。
    ui._latest_image = cv2.imread(str(Path(__file__).parent / "fixtures/ymjh/mining_coordinates/gathering_rain.png"))
    assert ui.click_acceleration_if_visible()
    assert ui.click_acceleration_if_visible()
    task.click_point.assert_called_once_with(637, 462, offset=0)


def test_stop_propagates_during_gather():
    """持续采集仍响应停止，不计成功。"""
    task = Mock()  # 初始未停止、第一次观察时收到停止请求。
    task.is_stopped.side_effect = [False, True]
    task._is_deadline_expired.return_value = False
    with pytest.raises(StepStopException):
        LifeFlow(task, Mock()).gather_once((935, 462))


@pytest.mark.parametrize('material', ['brass_ore', 'silver_ore', 'emerald_ore'])
def test_mining_entry_does_not_require_material_name_or_dismount(material):
    """参数：material 为配置矿种；坐标点有采集标志即可进入原采集流程。"""
    task = SHRWTask({'task_type':'mining', 'material':material})  # 仅使用配置选择坐标，不按矿名或坐骑过滤入口。
    task._vision = VisionEngine()
    frame = cv2.imread(str(Path(__file__).parent / 'fixtures/ymjh/mining_coordinates/hud_obstructed_1586_1778.png'))  # 矿名被坐骑遮住，但挖矿入口明确存在。
    assert task.find_configured_gather_action(frame) == task.POINT_GATHER_ACTIONS[0]


@pytest.mark.parametrize("name", ["empty_slope", "empty_906"])
def test_empty_terrain_is_not_mining_action(name):
    """参数：name 为没有采集入口但曾被亮色规则误判的真实场景。"""
    task = SHRWTask()  # 使用实际识图逻辑的挖矿任务。
    task._vision = VisionEngine()
    frame = cv2.imread(str(Path(__file__).parent / f"fixtures/ymjh/mining_coordinates/{name}.png"))  # 负例截图。
    assert task.find_configured_gather_action(frame) is None


@pytest.mark.parametrize('name', ['emerald_action', 'emerald_action_1481_1744'])
def test_real_emerald_action_is_preserved(name):
    """参数：name 为已人工核对矿点的真实帧；运行时只识别通用挖矿入口。"""
    task = SHRWTask({"task_type": "mining", "material": "emerald_ore"})  # 四级矿石实例。
    task._vision = VisionEngine()
    frame = cv2.imread(str(Path(__file__).parent / f"fixtures/ymjh/mining_coordinates/{name}.png"))  # 已核对资源名称的正例。
    assert task.find_configured_gather_action(frame) == task.POINT_GATHER_ACTIONS[0]



@pytest.mark.parametrize("name, expected", [("gathering_green", LifeSignal.GATHERING), ("finished_neighbor", LifeSignal.IDLE)])
def test_gathering_border_ignores_ground_background(name, expected):
    """参数：name 为真实帧；expected 为带邻矿入口时正确的采集状态。"""
    task = SHRWTask()  # 使用真实模板的测试任务。
    task._vision = VisionEngine()
    task.screenshot = Mock(return_value=cv2.imread(str(Path(__file__).parent / f"fixtures/ymjh/mining_coordinates/{name}.png")))
    assert LifeUI(task).observe().signal == expected




@pytest.mark.parametrize("name, expected", [("gathering_border_tail", LifeSignal.GATHERING), ("gathering_border_gone", LifeSignal.IDLE)])
def test_gathering_border_tail_must_finish(name, expected):
    """参数：name 为白边消退末段真实帧；expected 为预期状态，防止提前计数。"""
    task = SHRWTask()  # 实际识图实例。
    task._vision = VisionEngine()
    task.screenshot = Mock(return_value=cv2.imread(str(Path(__file__).parent / f"fixtures/ymjh/mining_coordinates/{name}.png")))
    assert LifeUI(task).observe().signal == expected













def test_gather_waits_for_progress_end_even_with_neighbor_action():
    """动作开始后需连续三帧空闲，邻矿按钮不妨碍结算。"""
    task = Mock()  # 使用有限状态序列而非设备的任务。
    task.is_stopped.return_value = False
    task._is_deadline_expired.return_value = False
    ui = Mock()  # 实际采集开始、短暂空闲、继续采集、稳定结束。
    ui.click_acceleration_if_visible.return_value = False
    ui.gather_completed.return_value = True
    ui.observe.side_effect = [
        LifeObservation(LifeSignal.IDLE),
        LifeObservation(LifeSignal.GATHERING),
        LifeObservation(LifeSignal.IDLE),
        LifeObservation(LifeSignal.GATHERING),
        *[LifeObservation(LifeSignal.IDLE, (935, 466))] * 3,
    ]
    LifeFlow(task, ui).gather_once((935, 466))
    assert ui.observe.call_count == 7


def test_missing_action_without_progress_is_not_success():
    """点击后无动作不能因按钮消失而计成功。"""
    task = Mock()  # 两帧之后截止的任务。
    task.is_stopped.return_value = False
    task._is_deadline_expired.side_effect = [False, False, True]
    ui = Mock()  # 一直空闲且无按钮的现场。
    ui.observe.return_value = LifeObservation(LifeSignal.IDLE)
    ui.click_acceleration_if_visible.return_value = False
    ui.gather_completed.return_value = True
    with pytest.raises(RuntimeError, match='未确认采集动作'):
        LifeFlow(task, ui).gather_once((935, 466))


def test_remaining_right_border_is_still_gathering():
    """左上进度已消退、右上仍有白边时不能提前结束。"""
    task = SHRWTask()  # 使用完整采集观察链路的任务。
    task._vision = VisionEngine()
    frame = cv2.imread(str(Path(__file__).parent / 'fixtures/ymjh/mining_coordinates/gathering_border_right.png'))  # 实测提前计数现场。
    task.screenshot = Mock(return_value=frame)
    assert LifeUI(task).observe().signal == LifeSignal.GATHERING


@pytest.mark.parametrize('occluded', [True, False])
def test_delayed_loot_popup_line_recovery_is_bounded(occluded):
    """参数：occluded 为是否确实检测到掉落提示，普通识别失败只等待重读，不执行关闭。"""
    task = Mock()  # 不连接设备的任务及关闭提示接口。
    task.is_stopped.return_value = False
    task._vision.match_template.return_value.found = occluded
    ui = LifeUI(task)  # 用失败序列验证恢复边界。
    ui.screenshot = Mock()
    ui.open_lines = Mock()
    ui.scroll_top = Mock(side_effect=RuntimeError('分线编号识别失败'))
    with pytest.raises(RuntimeError, match='分线编号识别失败'):
        ui.list_lines('interconnected')
    assert ui.open_lines.call_count == 3
    assert task.close_all_panels.call_count == (2 if occluded else 0)


def test_delayed_loot_popup_recovers_line_list():
    """确认遮挡后清理重开，返回重新识别的列表。"""
    task = Mock()  # 确认掉落提示存在的任务。
    task.is_stopped.return_value = False
    task._vision.match_template.return_value.found = True
    ui = LifeUI(task)  # 第一次读取失败，重开后成功。
    ui.screenshot = Mock()
    ui.open_lines = Mock()
    ui.scroll_top = Mock(side_effect=[RuntimeError('分线编号识别失败'), None])
    ui.visible_lines = Mock(return_value=[])
    assert ui.list_lines('interconnected') == []
    assert ui.open_lines.call_count == 2
    task.close_all_panels.assert_called_once()


def test_real_loot_overlay_has_recognizable_close_button():
    """实际遮挡线路编号的掉落提示可由公共关闭模板识别。"""
    task = SHRWTask()  # 复用生产关闭按钮素材。
    task._vision = VisionEngine()
    frame = cv2.imread(str(Path(__file__).parent / 'fixtures/ymjh/mining_coordinates/line_loot_overlay.png'))  # 延迟弹出提示的失败帧。
    assert task._vision.match_template(frame, task.GENERAL_CLOSE_TEMPLATES, threshold=0.85, roi=(1050, 210, 100, 80)).found


def test_change_line_uses_recoverable_list_read():
    """二次确认目标线路也必须走可恢复的共用读取入口。"""
    from ymjh_bot.task.SHRW_task import LifeLine
    task = Mock()  # 不连接设备的任务。
    ui = LifeUI(task)  # 被测换线操作器。
    ui.list_lines = Mock(return_value=[])
    assert not ui.change_line('interconnected', LifeLine(2, (980, 152), False, True))
    ui.list_lines.assert_called_once_with('interconnected')
    task.click_point.assert_not_called()


@pytest.mark.parametrize('name, expected', [('empty_slope', False), ('empty_906', False), ('finished_neighbor', True), ('gathering_border_gone', True)])
def test_loot_recovery_detection_real_scenes(name, expected):
    """参数：name 为真实截图；expected 表示是否存在掉落或配方提示。"""
    task = SHRWTask()  # 真实关闭模板与视觉引擎。
    task._vision = VisionEngine()
    frame = cv2.imread(str(Path(__file__).parent / f'fixtures/ymjh/mining_coordinates/{name}.png'))  # 对照截图。
    assert task._vision.match_template(frame, task.GENERAL_CLOSE_TEMPLATES, threshold=0.85, roi=(1050, 210, 100, 80)).found == expected


def test_silver_calibrated_position_has_action_for_all_mining_configs():
    """位置决定目标，采集入口识别不依赖矿种或工具等级。"""
    frame = cv2.imread(str(Path(__file__).parent / 'fixtures/ymjh/mining_coordinates/silver_action_1212_1586.png'))  # 已实机核对的银矿可采位置。
    for material in ('stone', 'brass_ore', 'silver_ore', 'gold_ore'):  # material 为配置矿种，不参与入口图标过滤。
        task = SHRWTask({'task_type':'mining', 'material':material})  # 各材料共用相同观察逻辑。
        task._vision = VisionEngine()
        assert task.find_configured_gather_action(frame) == (935, 466)


def test_progress_border_disappearing_without_settlement_cannot_complete():
    """末段白边漏检不等于动作完成，必须继续等待结算。"""
    task = Mock()  # 四次观察后到达截止时间。
    task.is_stopped.return_value = False
    task._is_deadline_expired.side_effect = [False] * 4 + [True]
    ui = Mock()  # 先有进度，随后三帧误判空闲，但始终没有结算。
    ui.observe.side_effect = [LifeObservation(LifeSignal.GATHERING)] + [LifeObservation(LifeSignal.IDLE)] * 3
    ui.click_acceleration_if_visible.return_value = False
    ui.gather_completed.return_value = False
    with pytest.raises(RuntimeError, match='未确认采集动作'):
        LifeFlow(task, ui).gather_once((935, 466))


@pytest.mark.parametrize('name, expected', [('gather_success', True), ('gather_success_gold', True), ('gathering_border_right', False), ('gathering_border_tail', False), ('empty_slope', False)])
def test_generic_settlement_real_frames(name, expected):
    """参数：name 为真实截图；expected 为是否出现通用采集结算文字。"""
    task = SHRWTask()  # 不按矿种筛选结算的真实视觉实例。
    task._vision = VisionEngine()
    ui = LifeUI(task)  # 复用生产结算检测器。
    ui._latest_image = cv2.imread(str(Path(__file__).parent / f'fixtures/ymjh/mining_coordinates/{name}.png'))
    assert ui.gather_completed() == expected


def test_hand_mining_entry_does_not_require_tool_icon():
    """手形入口只要有明确挖矿文字即可尝试，实际完成仍由动作与结算确认。"""
    task = SHRWTask({'task_type':'mining', 'material':'emerald_ore'})  # 不按工具等级筛选入口。
    task._vision = VisionEngine()
    frame = cv2.imread(str(Path(__file__).parent / 'fixtures/ymjh/mining_coordinates/mining_hand_action.png'))  # 真实手形挖矿入口。
    task.configured_gather_templates = Mock(side_effect=AssertionError('挖矿入口不依赖工具模板'))
    assert task.find_configured_gather_action(frame) == (935, 466)


def test_skill_requirement_is_explicit_unavailable_not_completion():
    """技能等级不足有明确停止原因，不能继续等待或计成功。"""
    from ymjh_bot.task.SHRW_task import LifeTaskUnavailable
    task = SHRWTask({'task_type':'mining', 'material':'tungsten_ore'})  # 实际五级矿配置。
    task._vision = VisionEngine()
    task.screenshot = Mock(return_value=cv2.imread(str(Path(__file__).parent / 'fixtures/ymjh/mining_coordinates/skill_required.png')))
    ui = LifeUI(task)  # 从真实提示帧读取限制状态。
    assert ui.observe().signal == LifeSignal.SKILL_LOCKED
    with pytest.raises(LifeTaskUnavailable, match='技能等级不足'):
        LifeFlow(task, ui).observe()
    assert task._successful_gathers == 0
