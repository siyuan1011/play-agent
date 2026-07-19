from __future__ import annotations

from pathlib import Path

import cv2
import pytest

from botCore import VisionEngine
from ymjh_bot.ym_game_task import YmGameTask


FIXTURES = Path(__file__).parent / "fixtures" / "ymjh"
VISION = VisionEngine()


def load_fixture(name: str):
    image = cv2.imread(str(FIXTURES / name), cv2.IMREAD_COLOR)
    assert image is not None
    return image


@pytest.mark.parametrize(
    ("fixture_name", "templates", "roi", "threshold", "minimum_score"),
    [
        (
            "unstuck_current_menu_closed_20260719.webp",
            [YmGameTask.BTN_QUICK_MENU_FLOWER, YmGameTask.BTN_QUICK_MENU_FLOWER_NEW],
            YmGameTask.ROI_QUICK_MENU_BUTTON,
            YmGameTask.ESCAPE_STUCK_MENU_THRESHOLD,
            0.8,
        ),
        (
            "unstuck_current_menu_open_20260719.webp",
            YmGameTask.BTN_ESCAPE_STUCK,
            YmGameTask.ROI_ESCAPE_STUCK_ITEM,
            YmGameTask.ESCAPE_STUCK_ITEM_THRESHOLD,
            0.8,
        ),
        (
            "unstuck_current_confirm_20260719.webp",
            YmGameTask.BTN_MODAL_OK,
            YmGameTask.ROI_CENTER_MODAL_OK,
            YmGameTask.ESCAPE_STUCK_CONFIRM_THRESHOLD,
            0.95,
        ),
    ],
)
def test_escape_stuck_templates_match_current_live_flow(
    fixture_name: str,
    templates: str | list[str],
    roi: tuple[int, int, int, int],
    threshold: float,
    minimum_score: float,
) -> None:
    match = VISION.match_template(
        load_fixture(fixture_name),
        templates,
        threshold=threshold,
        roi=roi,
    )

    assert match.found
    assert match.score >= minimum_score


@pytest.mark.parametrize(
    "fixture_name",
    [
        "scene_login_splash.webp",
        "门客设宴5.webp",
        "门客设宴7.webp",
    ],
)
def test_escape_stuck_menu_rejects_screens_without_quick_menu(fixture_name: str) -> None:
    match = VISION.match_template(
        load_fixture(fixture_name),
        [YmGameTask.BTN_QUICK_MENU_FLOWER, YmGameTask.BTN_QUICK_MENU_FLOWER_NEW],
        threshold=YmGameTask.ESCAPE_STUCK_MENU_THRESHOLD,
        roi=YmGameTask.ROI_QUICK_MENU_BUTTON,
    )

    assert not match.found


def test_escape_stuck_full_image_flow_uses_current_live_states(monkeypatch) -> None:
    task = YmGameTask()
    task._screen_resolution = task.FIXED_RESOLUTION
    task._vision = VISION
    screens = {
        "closed": load_fixture("unstuck_current_menu_closed_20260719.webp"),
        "menu": load_fixture("unstuck_current_menu_open_20260719.webp"),
        "confirm": load_fixture("unstuck_current_confirm_20260719.webp"),
    }
    state = ["closed"]
    clicked_centers: list[tuple[int, int] | None] = []

    monkeypatch.setattr(task, "screenshot", lambda: screens[state[0]])
    monkeypatch.setattr(task, "wait", lambda ms: None)

    def click(*, offset: int = 3) -> None:
        clicked_centers.append(task._last_match_center)
        if state[0] == "closed":
            state[0] = "menu"
        elif state[0] == "menu":
            state[0] = "confirm"
        elif state[0] == "confirm":
            state[0] = "done"

    monkeypatch.setattr(task, "click", click)

    assert task._try_escape_stuck_once(attempt=1) is True
    assert state == ["done"]
    assert clicked_centers == [(59, 662), (296, 508), (854, 508)]
