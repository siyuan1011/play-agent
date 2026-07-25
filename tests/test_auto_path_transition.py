from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from botCore import ImageMatchResult, VisionEngine
from botCore.vision import load_image
from ymjh_bot.ym_game_task import YmGameTask


FIXTURES = Path(__file__).parent / "fixtures" / "ymjh"
VISION = VisionEngine()


def make_match(found: bool, template: str, score: float) -> ImageMatchResult:
    center = (100, 50) if found else None
    bbox = (90, 40, 110, 60) if found else None
    return ImageMatchResult(
        found=found,
        score=score,
        center=center,
        bbox=bbox,
        template_path=template,
    )


class TransitionVision:
    """Map a frame marker to auto-path/loading matches."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    def match_template(self, screenshot, template_paths, *, threshold=0.85, roi=None):
        frame = int(screenshot[0, 0, 0])
        templates = [template_paths] if isinstance(template_paths, str) else template_paths
        template = str(templates[0])
        if template == YmGameTask.TEXT_AUTO_PATH:
            kind = "path"
            found = frame in {1, 3}
        elif templates == YmGameTask.SCENE_LOADING_LOGO_TEMPLATES:
            kind = "loading"
            found = frame in {2, 3}
        else:
            raise AssertionError(f"unexpected template: {template}")

        self.calls.append((frame, kind))
        return make_match(found, template, 0.98 if found else 0.2)


def setup_transition_task(monkeypatch, frames: list[int]) -> tuple[YmGameTask, list[int]]:
    task = YmGameTask()
    task._vision = TransitionVision()
    screenshot_calls: list[int] = []
    frame_iter = iter(frames)
    last_frame = frames[-1]

    def screenshot() -> np.ndarray:
        nonlocal last_frame
        last_frame = next(frame_iter, last_frame)
        screenshot_calls.append(last_frame)
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        image[0, 0, 0] = last_frame
        return image

    monkeypatch.setattr(task, "screenshot", screenshot)
    monkeypatch.setattr(task, "wait", lambda ms: None)
    return task, screenshot_calls


def test_wait_auto_pathfinding_covers_path_loading_and_stable_frames(monkeypatch) -> None:
    task, screenshot_calls = setup_transition_task(monkeypatch, [1, 1, 2, 2, 0, 0, 0])

    assert task.wait_auto_pathfinding(timeout_ms=None) is True
    assert screenshot_calls == [1, 1, 2, 2, 0, 0, 0]
    assert task._vision.calls == [
        (frame, kind)
        for frame in screenshot_calls
        for kind in ("path", "loading")
    ]


def test_wait_auto_pathfinding_handles_loading_already_in_progress(monkeypatch) -> None:
    task, screenshot_calls = setup_transition_task(monkeypatch, [2, 2, 0, 0, 0])

    assert task.wait_auto_pathfinding(timeout_ms=None) is True
    assert screenshot_calls == [2, 2, 0, 0, 0]


def test_wait_auto_pathfinding_keeps_original_three_missing_frame_semantics(monkeypatch) -> None:
    task, screenshot_calls = setup_transition_task(monkeypatch, [0, 0, 0])

    assert task.wait_auto_pathfinding(timeout_ms=None) is True
    assert screenshot_calls == [0, 0, 0]


def test_wait_auto_pathfinding_returns_false_when_loading_times_out(monkeypatch) -> None:
    task, screenshot_calls = setup_transition_task(monkeypatch, [2])
    clock = [0.0]

    monkeypatch.setattr("ymjh_bot.ym_game_task.time.perf_counter", lambda: clock[0])
    monkeypatch.setattr(task, "wait", lambda ms: clock.__setitem__(0, clock[0] + ms / 1000))

    assert task.wait_auto_pathfinding(timeout_ms=1000) is False
    assert screenshot_calls == [2, 2]


@pytest.mark.parametrize(
    ("fixture_name", "minimum_score"),
    [
        ("scene_loading_02.webp", 0.99),
        ("scene_loading_95.webp", 0.8),
    ],
)
def test_scene_loading_logo_matches_real_loading_frames(
    fixture_name: str,
    minimum_score: float,
) -> None:
    match = VISION.match_template(
        load_image(FIXTURES / fixture_name),
        YmGameTask.SCENE_LOADING_LOGO_TEMPLATES,
        threshold=YmGameTask.SCENE_LOADING_THRESHOLD,
        roi=YmGameTask.ROI_SCENE_LOADING_LOGO,
    )

    assert match.found
    assert match.score >= minimum_score


@pytest.mark.parametrize(
    "fixture",
    [
        FIXTURES / "scene_login_splash.webp",
        FIXTURES / "bprw_sidebar_return.webp",
        FIXTURES / "kyrw_keye_20260707" / "51_keye_complete_dialog.webp",
        FIXTURES / "门客设宴6.webp",
    ],
)
def test_scene_loading_logo_rejects_non_loading_screens(fixture: Path) -> None:
    match = VISION.match_template(
        load_image(fixture),
        YmGameTask.SCENE_LOADING_LOGO_TEMPLATES,
        threshold=YmGameTask.SCENE_LOADING_THRESHOLD,
        roi=YmGameTask.ROI_SCENE_LOADING_LOGO,
    )

    assert not match.found


def test_scene_loading_template_set_uses_both_new_logos() -> None:
    expected_templates = [
        str(YmGameTask.TEMPLATES_DIR / "text_scene_loading_logo1.png"),
        str(YmGameTask.TEMPLATES_DIR / "text_scene_loading_logo2.png"),
    ]

    assert YmGameTask.SCENE_LOADING_LOGO_TEMPLATES == expected_templates
    assert all(Path(template).is_file() for template in expected_templates)


def test_second_scene_loading_logo_participates_in_matching() -> None:
    second_template = load_image(YmGameTask.TEXT_SCENE_LOADING_LOGO2)
    screenshot = np.zeros((170, 430, 3), dtype=np.uint8)
    height, width = second_template.shape[:2]
    screenshot[20 : 20 + height, 90 : 90 + width] = second_template

    match = VISION.match_template(
        screenshot,
        YmGameTask.SCENE_LOADING_LOGO_TEMPLATES,
        threshold=YmGameTask.SCENE_LOADING_THRESHOLD,
        roi=YmGameTask.ROI_SCENE_LOADING_LOGO,
    )

    assert match.found
    assert match.template_path == YmGameTask.TEXT_SCENE_LOADING_LOGO2
