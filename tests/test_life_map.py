"""生活任务地图误判回归：复用安全区的世界/区域模板。"""
from pathlib import Path
from unittest.mock import Mock

import cv2
import pytest
from botCore import StepStopException
from ymjh_bot.task.SHRW_task import SHRWTask

FIXTURES = Path(__file__).parent / "fixtures/ymjh/life_map"  # 失败现场及实机切图帧。


@pytest.mark.parametrize("name, expected", [
    ("region_0", True), ("region_1", True), ("region_2", True),
    ("world", True), ("main", False),
])
def test_map_markers(name, expected):
    """参数：name 为截图名；expected 为是否应识别到已打开的地图。"""
    frame = cv2.imread(str(FIXTURES / f"{name}.png"))  # 固定分辨率真实帧。
    assert frame is not None
    assert SHRWTask.is_map_visible(frame) is expected


@pytest.mark.parametrize("name", ["region_0", "world"])
def test_open_map_does_not_click_open_map_again(name):
    """参数：name 为已打开的区域地图或世界地图现场。"""
    task = SHRWTask()  # 独立导航验证实例。
    task.screenshot = Mock(return_value=cv2.imread(str(FIXTURES / f"{name}.png")))
    task.ensure_local_map_open = Mock()
    task.open_map()
    task.ensure_local_map_open.assert_not_called()


def test_open_map_uses_shared_navigation_and_propagates_stop():
    """未打开地图时使用公共入口，保留停止异常。"""
    task = SHRWTask()  # 不连接设备的导航实例。
    task.screenshot = Mock(return_value=cv2.imread(str(FIXTURES / "main.png")))
    task.wake_from_power_saving_if_needed = Mock()
    task.ensure_local_map_open = Mock(side_effect=StepStopException())
    with pytest.raises(StepStopException):
        task.open_map()
    task.ensure_local_map_open.assert_called_once_with(wait_after_click_ms=task.MAP_WAIT_MS)
