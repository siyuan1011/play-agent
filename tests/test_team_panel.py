from __future__ import annotations

import numpy as np
import pytest

from ymjh_bot.ym_game_task import YmGameTask


@pytest.mark.parametrize(
    ("visible_templates", "expected_state"),
    [
        ({YmGameTask.TEXT_TEAM_PANEL_TITLE}, (True, False)),
        ({YmGameTask.BTN_TEAM_LEAVE}, (True, True)),
        (set(), (False, False)),
    ],
)
def test_normal_team_panel_state_uses_one_frame_and_two_markers(
    visible_templates: set[str],
    expected_state: tuple[bool, bool],
) -> None:
    task = YmGameTask()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    calls: list[tuple[str, np.ndarray | None]] = []

    def find_image(template: str, **kwargs) -> bool:
        calls.append((template, kwargs.get("screenshot")))
        return template in visible_templates

    task.find_image = find_image  # type: ignore[method-assign]
    task.screenshot = lambda: pytest.fail("不应重新截图")  # type: ignore[method-assign]

    assert task._read_normal_team_panel_state(frame) == expected_state
    assert [template for template, _ in calls] == [
        task.TEXT_TEAM_PANEL_TITLE,
        task.BTN_TEAM_LEAVE,
    ]
    assert all(screenshot is frame for _, screenshot in calls)


def test_wait_for_team_panel_open_uses_common_wait_helper() -> None:
    task = YmGameTask()
    calls: list[tuple[object, dict[str, object]]] = []
    task.wait_image_appear = lambda template, **kwargs: (  # type: ignore[method-assign]
        calls.append((template, kwargs)) or True
    )

    assert task.wait_for_team_panel_open(timeout_ms=2500)
    assert calls == [
        (
            task.TEXT_TEAM_PANEL_TITLE,
            {
                "timeout_ms": 2500,
                "threshold": task.TEAM_TEMPLATE_THRESHOLD,
                "interval_ms": 250,
                "roi": task.scale_roi(task.ROI_TEAM_PANEL_TITLE),
            },
        )
    ]


def test_team_matching_and_member_count_reuse_supplied_frame() -> None:
    task = YmGameTask()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    calls: list[tuple[str, np.ndarray | None]] = []

    def find_image(template: str, **kwargs) -> bool:
        calls.append((template, kwargs.get("screenshot")))
        if template == task.BTN_TEAM_CANCEL_MATCH:
            return True
        return len(
            [called_template for called_template, _ in calls if called_template == template]
        ) <= 2

    task.find_image = find_image  # type: ignore[method-assign]
    task.screenshot = lambda: pytest.fail("不应重新截图")  # type: ignore[method-assign]

    assert task.is_team_matching(frame)
    assert task.count_team_members(frame) == len(task.ROI_TEAM_MEMBER_SLOTS) - 2
    assert all(screenshot is frame for _, screenshot in calls)


def test_click_team_shout_uses_common_match_center() -> None:
    task = YmGameTask()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    clicks: list[int] = []

    def find_image(_template: str, **kwargs) -> bool:
        assert kwargs["screenshot"] is frame
        task._last_match_center = (612, 116)
        return True

    task.find_image = find_image  # type: ignore[method-assign]
    task.screenshot = lambda: pytest.fail("不应重新截图")  # type: ignore[method-assign]
    task.click = lambda offset=3: clicks.append(offset)  # type: ignore[method-assign]
    task.click_point = lambda *_args, **_kwargs: pytest.fail(  # type: ignore[method-assign]
        "不应使用兜底坐标"
    )

    task.click_team_shout(frame)

    assert clicks == [0]
