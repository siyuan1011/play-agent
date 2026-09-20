from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from botCore import ImageMatchResult, VisionEngine
from botCore.vision import load_image
from ymjh_bot.ym_game_task import TaskSidebarSnapshot, TaskSidebarStateError, YmGameTask


class _PowerSavingTask(YmGameTask):
    task_name = "省电模式检测测试"


class _ScoreVision:
    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores
        self.calls: list[
            tuple[
                np.ndarray,
                str | list[str],
                float,
                tuple[int, int, int, int],
            ]
        ] = []

    def match_template(
        self,
        screenshot: np.ndarray,
        template: str | list[str],
        *,
        threshold: float,
        roi: tuple[int, int, int, int],
    ) -> ImageMatchResult:
        self.calls.append((screenshot, template, threshold, roi))
        templates = [template] if isinstance(template, str) else template
        scores = [
            self.scores.get(Path(candidate).stem.rsplit("_", 1)[-1], 0.0)
            for candidate in templates
        ]
        score = max(scores, default=0.0)
        return ImageMatchResult(
            found=score >= threshold,
            score=score,
            center=(10, 10) if score >= threshold else None,
            bbox=None,
            template_path=templates[scores.index(score)] if scores else None,
        )


def _task_with_scores(scores: dict[str, float]) -> tuple[_PowerSavingTask, _ScoreVision]:
    task = _PowerSavingTask()
    vision = _ScoreVision(scores)
    task._vision = vision  # type: ignore[assignment]
    task.screenshot = lambda: np.zeros((720, 1280, 3), dtype=np.uint8)  # type: ignore[method-assign]
    return task, vision


@pytest.mark.parametrize("middle_character", ["dian", "mo", "shi"])
def test_power_saving_requires_both_anchors_and_any_middle_character(
    middle_character: str,
) -> None:
    scores = {"sheng": 0.8, "dian": 0.79, "mo": 0.79, "shi": 0.79, "zhong": 0.8}
    scores[middle_character] = 0.8
    task, vision = _task_with_scores(scores)

    assert task.is_power_saving_mode(np.zeros((720, 1280, 3), dtype=np.uint8))
    assert len(vision.calls) == 9


@pytest.mark.parametrize(
    "scores",
    [
        {"sheng": 0.7499, "dian": 0.9, "mo": 0.9, "shi": 0.9, "zhong": 0.9},
        {"sheng": 0.9, "dian": 0.9, "mo": 0.9, "shi": 0.9, "zhong": 0.7499},
        {"sheng": 0.9, "dian": 0.7499, "mo": 0.7499, "shi": 0.7499, "zhong": 0.9},
    ],
)
def test_power_saving_rejects_missing_anchor_or_middle_match(scores: dict[str, float]) -> None:
    task, vision = _task_with_scores(scores)

    assert not task.is_power_saving_mode(np.zeros((720, 1280, 3), dtype=np.uint8))
    assert len(vision.calls) == 3


def test_power_saving_uses_one_frame_per_round_for_three_rounds() -> None:
    scores = {name: 0.9 for name in ("sheng", "dian", "mo", "shi", "zhong")}
    task, vision = _task_with_scores(scores)
    frames = [np.full((720, 1280, 3), index, dtype=np.uint8) for index in range(3)]
    screenshot_iter = iter(frames)
    task.screenshot = lambda: next(screenshot_iter)  # type: ignore[method-assign]

    assert task.is_power_saving_mode()
    assert len(vision.calls) == 9
    for index, frame in enumerate(frames):
        round_calls = vision.calls[index * 3 : index * 3 + 3]
        assert all(call[0] is frame for call in round_calls)
        assert round_calls[0][1] == [task.TEXT_POWER_SAVING_SHENG]
        assert round_calls[1][1] == [task.TEXT_POWER_SAVING_ZHONG]
        assert round_calls[2][1] == [
            task.TEXT_POWER_SAVING_DIAN,
            task.TEXT_POWER_SAVING_MO,
            task.TEXT_POWER_SAVING_SHI,
        ]
        assert all(call[2] == 0.75 for call in round_calls)


def test_power_saving_uses_supplied_screenshot_only_for_first_round() -> None:
    scores = {name: 0.9 for name in ("sheng", "dian", "mo", "shi", "zhong")}
    task, vision = _task_with_scores(scores)
    supplied = np.zeros((720, 1280, 3), dtype=np.uint8)
    captured = [
        np.ones((720, 1280, 3), dtype=np.uint8),
        np.full((720, 1280, 3), 2, dtype=np.uint8),
    ]
    screenshot_calls = 0

    def screenshot() -> np.ndarray:
        nonlocal screenshot_calls
        frame = captured[screenshot_calls]
        screenshot_calls += 1
        return frame

    task.screenshot = screenshot  # type: ignore[method-assign]

    assert task.is_power_saving_mode(supplied)
    assert screenshot_calls == 2
    assert all(call[0] is supplied for call in vision.calls[:3])
    assert all(call[0] is captured[0] for call in vision.calls[3:6])
    assert all(call[0] is captured[1] for call in vision.calls[6:9])


def test_power_saving_rejects_when_a_later_confirmation_frame_fails() -> None:
    task = _PowerSavingTask()
    frames = [np.full((720, 1280, 3), index, dtype=np.uint8) for index in range(3)]
    screenshot_calls = 0

    class _LaterFailureVision(_ScoreVision):
        def match_template(self, screenshot, template, *, threshold, roi):
            original_scores = self.scores
            if int(screenshot[0, 0, 0]) == 1:
                self.scores = {**original_scores, "sheng": 0.74}
            try:
                return super().match_template(
                    screenshot,
                    template,
                    threshold=threshold,
                    roi=roi,
                )
            finally:
                self.scores = original_scores

    vision = _LaterFailureVision(
        {name: 0.9 for name in ("sheng", "dian", "mo", "shi", "zhong")}
    )
    task._vision = vision  # type: ignore[assignment]

    def screenshot() -> np.ndarray:
        nonlocal screenshot_calls
        frame = frames[screenshot_calls]
        screenshot_calls += 1
        return frame

    task.screenshot = screenshot  # type: ignore[method-assign]

    assert not task.is_power_saving_mode()
    assert screenshot_calls == 2
    assert len(vision.calls) == 6


def _frame_from_power_saving_fixture(name: str) -> np.ndarray:
    roi = load_image(Path(__file__).parent / "fixtures" / "power_saving" / name)
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[470:610, 480:820] = roi
    return frame


@pytest.mark.parametrize(
    "fixture_name",
    [
        "positive_dian_0793.png",
        "positive_shi_0793.png",
        "positive_dian_0787.png",
    ],
)
def test_power_saving_visual_regression_accepts_hard_positive_frames(
    fixture_name: str,
) -> None:
    task = _PowerSavingTask()
    task._vision = VisionEngine()
    frame = _frame_from_power_saving_fixture(fixture_name)
    task.screenshot = lambda: frame  # type: ignore[method-assign]

    assert task.is_power_saving_mode(frame)


def test_power_saving_visual_regression_rejects_calendar_item_popup() -> None:
    task = _PowerSavingTask()
    task._vision = VisionEngine()
    frame = _frame_from_power_saving_fixture("negative_calendar_item_popup.png")
    task.screenshot = lambda: frame  # type: ignore[method-assign]

    assert not task.is_power_saving_mode(frame)


def test_power_saving_missing_anchor_template_is_not_a_match() -> None:
    task = _PowerSavingTask()
    task._vision = VisionEngine()
    specs = list(task.POWER_SAVING_CHARACTER_SPECS)
    character, _, roi = specs[0]
    missing_template = Path(__file__).parent / "fixtures" / "power_saving" / "missing-sheng.png"
    assert not missing_template.exists()
    specs[0] = (character, str(missing_template), roi)
    task.POWER_SAVING_CHARACTER_SPECS = tuple(specs)
    frame = _frame_from_power_saving_fixture("positive_dian_0793.png")
    task.screenshot = lambda: frame  # type: ignore[method-assign]

    assert not task.is_power_saving_mode(frame)


def test_power_saving_templates_have_tight_expected_dimensions() -> None:
    expected_sizes = {
        "省": (24, 22),
        "电": (22, 22),
        "模": (23, 24),
        "式": (24, 21),
        "中": (24, 19),
    }

    for character, template, _ in _PowerSavingTask.POWER_SAVING_CHARACTER_SPECS:
        assert load_image(template).shape[:2] == expected_sizes[character]


def test_task_sidebar_gate_checks_power_saving_against_snapshot_image() -> None:
    task = _PowerSavingTask()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    no_match = ImageMatchResult(False, 0.0, None, None)
    snapshot = TaskSidebarSnapshot(
        image=frame,
        active_panel=None,
        active_matches={},
        entry_match=no_match,
        expand_match=no_match,
        fullscreen_match=no_match,
    )
    inspected_frames: list[np.ndarray | None] = []
    task.is_power_saving_mode = (  # type: ignore[method-assign]
        lambda screenshot=None: inspected_frames.append(screenshot) or True
    )

    def raise_state_error(
        description: str,
        image: np.ndarray,
        matches: dict[str, ImageMatchResult],
    ) -> None:
        raise TaskSidebarStateError(description)

    task._raise_task_sidebar_state_error = raise_state_error  # type: ignore[method-assign]

    with pytest.raises(TaskSidebarStateError, match="省电状态"):
        task._verify_default_task_sidebar_activation_gate(
            snapshot,
            time.perf_counter() + 1,
        )

    assert inspected_frames == [frame]
