from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from botCore import ImageMatchResult, RunLogger
from ymjh_bot.ym_game_task import YmGameTask


def make_match(
    center: tuple[int, int],
    score: float,
    template: str = "close.png",
) -> ImageMatchResult:
    x, y = center
    return ImageMatchResult(
        found=True,
        score=score,
        center=center,
        bbox=(x - 10, y - 10, x + 10, y + 10),
        template_path=template,
    )


class FrameVision:
    def __init__(self, candidates_by_frame: dict[int, list[ImageMatchResult]]) -> None:
        self.candidates_by_frame = candidates_by_frame

    def match_all_templates(self, screenshot, template_paths, *, threshold=0.85, roi=None):
        return list(self.candidates_by_frame.get(id(screenshot), []))


class CloseTask(YmGameTask):
    def __init__(
        self,
        frames: list[np.ndarray],
        candidates_by_frame: dict[int, list[ImageMatchResult]],
        *,
        logger: RunLogger | None = None,
    ) -> None:
        super().__init__()
        self.frames = frames
        self.frame_index = 0
        self.taps: list[tuple[int, int]] = []
        self._vision = FrameVision(candidates_by_frame)
        self._logger = logger

    def screenshot(self) -> np.ndarray:
        index = min(self.frame_index, len(self.frames) - 1)
        self.frame_index += 1
        return self.frames[index]

    def tap(self, x: int | None = None, y: int | None = None) -> None:
        assert x is not None and y is not None
        self.taps.append((x, y))

    def wait(self, ms: int | float) -> None:
        return None

    def collapse_chat_if_open(self, wait_after_click_ms: int = 800) -> bool:
        return False


def test_dual_close_tries_blocked_high_score_then_foreground_then_next_layer() -> None:
    foreground = np.zeros((720, 1280, 3), dtype=np.uint8)
    no_effect = foreground.copy()
    calendar = np.full_like(foreground, 180)
    main = np.full_like(foreground, 40)
    outer = make_match((1206, 49), 0.976)
    inner = make_match((1131, 103), 0.945)
    task = CloseTask(
        [foreground, no_effect, calendar, main, main],
        {
            id(foreground): [outer, inner],
            id(no_effect): [outer, inner],
            id(calendar): [outer],
            id(main): [],
        },
    )

    task.close_all_panels(timeout_ms=0)

    assert task.taps == [(1206, 49), (1131, 103), (1206, 49)]


def test_same_position_close_is_retried_when_page_structure_changes() -> None:
    first = np.zeros((720, 1280, 3), dtype=np.uint8)
    second = np.full_like(first, 180)
    final = np.full_like(first, 40)
    close = make_match((1200, 50), 0.97)
    task = CloseTask(
        [first, second, final, final],
        {id(first): [close], id(second): [close], id(final): []},
    )

    task.close_all_panels(timeout_ms=0)

    assert task.taps == [(1200, 50), (1200, 50)]


def test_coordinate_set_uses_ten_pixel_tolerance() -> None:
    task = YmGameTask()

    assert task._same_close_candidate_centers(
        [make_match((100, 100), 0.99)],
        [make_match((106, 108), 0.80)],
    )
    assert not task._same_close_candidate_centers(
        [make_match((100, 100), 0.99)],
        [make_match((107, 108), 0.80)],
    )


def test_same_count_with_coordinate_change_is_a_new_state() -> None:
    task = YmGameTask()

    assert not task._same_close_candidate_centers(
        [make_match((1206, 49), 0.97), make_match((1131, 103), 0.94)],
        [make_match((1206, 49), 0.97), make_match((1100, 103), 0.94)],
    )


def test_close_candidates_from_multiple_templates_are_merged_within_18_pixels() -> None:
    task = YmGameTask()
    candidates = [
        make_match((100, 100), 0.95, "welcome.png"),
        make_match((109, 109), 0.90, "close.png"),
        make_match((120, 100), 0.85, "pane.png"),
    ]

    merged = task._merge_close_candidates(candidates)

    assert [(item.center, item.score) for item in merged] == [
        ((100, 100), 0.95),
        ((120, 100), 0.85),
    ]


def test_three_unchanged_clicks_save_annotated_screenshot_and_raise(tmp_path: Path) -> None:
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    outer = make_match((1206, 49), 0.976)
    inner = make_match((1131, 103), 0.945)
    logger = RunLogger(tmp_path, retention_days=None)
    task = CloseTask([frame], {id(frame): [outer, inner]}, logger=logger)

    with pytest.raises(RuntimeError, match="连续三次关闭点击未改变界面"):
        task.close_all_panels(timeout_ms=0)

    assert task.taps == [(1206, 49), (1131, 103), (1206, 49)]
    assert len(list(logger.shots_dir.glob("close_panels_failed_*.png"))) == 1


def test_total_click_budget_saves_screenshot_and_raises(tmp_path: Path) -> None:
    first = np.zeros((720, 1280, 3), dtype=np.uint8)
    second = np.full_like(first, 180)
    close = make_match((1206, 49), 0.976)
    logger = RunLogger(tmp_path, retention_days=None)
    task = CloseTask(
        [first, second, first],
        {id(first): [close], id(second): [close]},
        logger=logger,
    )

    with pytest.raises(RuntimeError, match="关闭弹窗达到总点击上限"):
        task.close_all_panels(timeout_ms=0, max_attempts=2)

    assert task.taps == [(1206, 49), (1206, 49)]
    assert len(list(logger.shots_dir.glob("close_panels_failed_*.png"))) == 1


def test_two_initial_frames_without_candidates_finish_without_clicking() -> None:
    empty = np.zeros((720, 1280, 3), dtype=np.uint8)
    task = CloseTask([empty, empty], {id(empty): []})

    task.close_all_panels(timeout_ms=0)

    assert task.taps == []
    assert task.frame_index == 2
