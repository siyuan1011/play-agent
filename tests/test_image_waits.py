from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pytest

from botCore import GameTask, ImageMatchResult


class _Vision:
    def __init__(self, *, found: bool = True) -> None:
        self.found = found
        self.images: list[np.ndarray] = []

    def match_template(
        self,
        screenshot: np.ndarray,
        _templates: list[str],
        *,
        threshold: float,
        roi: tuple[int, int, int, int] | None,
    ) -> ImageMatchResult:
        self.images.append(screenshot)
        return ImageMatchResult(
            found=self.found,
            score=threshold if self.found else 0.0,
            center=(25, 30) if self.found else None,
            bbox=None,
        )


def _task_with_find_results(results: list[bool]) -> tuple[GameTask, list[bool]]:
    task = GameTask()
    remaining: Iterator[bool] = iter(results)
    calls: list[bool] = []

    def find_image(*_args, **_kwargs) -> bool:
        found = next(remaining)
        calls.append(found)
        task._last_match_center = (len(calls), len(calls)) if found else None
        return found

    task.find_image = find_image  # type: ignore[method-assign]
    task.wait = lambda _ms: None  # type: ignore[method-assign]
    return task, calls


def test_find_image_uses_supplied_screenshot_without_recapturing() -> None:
    task = GameTask()
    vision = _Vision()
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    task._vision = vision  # type: ignore[assignment]
    task.screenshot = lambda: pytest.fail("不应重新截图")  # type: ignore[method-assign]

    assert task.find_image("template.png", screenshot=frame)
    assert vision.images == [frame]
    assert task._last_match_center == (25, 30)


def test_wait_image_appear_default_remains_one_hit() -> None:
    task, calls = _task_with_find_results([True])

    assert task.wait_image_appear("template.png", timeout_ms=None)
    assert calls == [True]
    assert task._last_match_center == (1, 1)


def test_wait_image_appear_reuses_supplied_screenshot_for_every_confirmation() -> None:
    task = GameTask()
    vision = _Vision()
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    task._vision = vision  # type: ignore[assignment]
    task.screenshot = lambda: pytest.fail("不应重新截图")  # type: ignore[method-assign]
    task.wait = lambda _ms: None  # type: ignore[method-assign]

    assert task.wait_image_appear(
        "template.png",
        timeout_ms=None,
        interval_ms=0,
        appear_threshold=3,
        appear_mode="consecutive",
        screenshot=frame,
    )
    assert len(vision.images) == 3
    assert all(image is frame for image in vision.images)


def test_wait_image_missing_reuses_supplied_screenshot_for_every_confirmation() -> None:
    task = GameTask()
    vision = _Vision(found=False)
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    task._vision = vision  # type: ignore[assignment]
    task.screenshot = lambda: pytest.fail("不应重新截图")  # type: ignore[method-assign]
    task.wait = lambda _ms: None  # type: ignore[method-assign]

    assert task.wait_image_missing(
        "template.png",
        timeout_ms=None,
        interval_ms=0,
        missing_threshold=3,
        screenshot=frame,
    )
    assert len(vision.images) == 3
    assert all(image is frame for image in vision.images)


def test_wait_image_appear_total_mode_accumulates_nonconsecutive_hits() -> None:
    task, calls = _task_with_find_results([True, False, True, False, True])
    callback_results: list[bool] = []

    assert task.wait_image_appear(
        "template.png",
        timeout_ms=None,
        interval_ms=0,
        callback=callback_results.append,
        appear_threshold=3,
        appear_mode="total",
    )
    assert calls == [True, False, True, False, True]
    assert callback_results == calls
    assert task._last_match_center == (5, 5)


def test_wait_image_appear_consecutive_mode_resets_after_a_miss() -> None:
    task, calls = _task_with_find_results([True, True, False, True, True, True])

    assert task.wait_image_appear(
        "template.png",
        timeout_ms=None,
        interval_ms=0,
        appear_threshold=3,
        appear_mode="consecutive",
    )
    assert calls == [True, True, False, True, True, True]
    assert task._last_match_center == (6, 6)


def test_wait_image_appear_timeout_clears_match_center_and_reports_false() -> None:
    task = GameTask()
    task._last_match_center = (10, 10)
    callback_results: list[bool] = []

    assert not task.wait_image_appear(
        "template.png",
        timeout_ms=0,
        callback=callback_results.append,
        appear_threshold=2,
    )
    assert task._last_match_center is None
    assert callback_results == [False]


@pytest.mark.parametrize(
    ("appear_threshold", "appear_mode"),
    [
        (0, "total"),
        (-1, "consecutive"),
        (1, "unknown"),
    ],
)
def test_wait_image_appear_rejects_invalid_confirmation_options_before_matching(
    appear_threshold: int,
    appear_mode: str,
) -> None:
    task = GameTask()
    task.find_image = lambda *_args, **_kwargs: pytest.fail(  # type: ignore[method-assign]
        "参数无效时不应找图"
    )

    with pytest.raises(ValueError):
        task.wait_image_appear(
            "template.png",
            appear_threshold=appear_threshold,
            appear_mode=appear_mode,  # type: ignore[arg-type]
        )
