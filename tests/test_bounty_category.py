"""悬赏分类与接取边界回归。"""
from pathlib import Path
from unittest.mock import Mock

import cv2
import pytest
from botCore import VisionEngine
from ymjh_bot.task.XSRW_task import XSRWTask, BountyCardSnapshot, BountyPanelSnapshot

FIXTURES = Path(__file__).parent / "fixtures/ymjh/bounty_category"  # 三种真实面板状态。


@pytest.mark.parametrize("name, expected", [("current", False), ("daily", False), ("unclassified", True)])
def test_unchecked_category(name, expected):
    """参数：name 为现场帧名称；expected 为是否需要启用分类。"""
    frame = cv2.imread(str(FIXTURES / f"{name}.png"))  # 现场帧。
    result = VisionEngine().match_template(
        frame, str(XSRWTask.TEMPLATES_DIR / "xsrw_category_unchecked.png"),
        threshold=0.95, roi=(770, 110, 55, 60),
    )  # 未勾选状态匹配结果。
    assert result.found is expected


def test_refuse_jypy_before_any_device_action():
    """聚义即使奖励达标也不得被接取。"""
    task = XSRWTask()  # 无设备测试实例。
    task.tap = Mock()
    card = BountyCardSnapshot(0, "聚义平冤", 4, True, "接取", (360, 510))  # 达标聚义卡。
    snapshot = BountyPanelSnapshot(None, True, False, (card,))  # 不参与视觉计算的状态。
    assert not snapshot.acceptable_cards
    with pytest.raises(ValueError):
        task.attempt_accept_bounty(snapshot, card)
    task.tap.assert_not_called()


@pytest.mark.parametrize("name, expected", [("current", True), ("daily", False), ("unclassified", False)])
def test_daily_category_tile(name, expected):
    """参数：name 为现场帧；expected 为是否展示可点击的日常分类标题。"""
    frame = cv2.imread(str(FIXTURES / f"{name}.png"))  # 分类页或卡片列表现场。
    result = VisionEngine().match_template(
        frame, str(XSRWTask.TEMPLATES_DIR / "xsrw_category_daily.png"),
        threshold=0.90, roi=(260, 175, 880, 360),
    )  # 分类文字匹配结果，卡片上的白色日常不能命中。
    assert result.found is expected
