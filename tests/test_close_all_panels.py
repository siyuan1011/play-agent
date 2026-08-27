from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from botCore import ImageMatchResult, RunLogger, VisionEngine, load_image
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
        self.calendar_prepare_calls = 0
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

    def collapse_emotion_panel_if_open(self, **kwargs) -> bool:
        return False

    def _prepare_jianghu_calendar_close(self) -> None:
        self.calendar_prepare_calls += 1


class RealCalendarCloseTask(YmGameTask):
    def __init__(self, frames: list[np.ndarray]) -> None:
        super().__init__()
        self.frames = frames
        self.frame_index = 0
        self.actions: list[tuple[str, tuple[int, int]]] = []
        self.logs: list[str] = []
        self._vision = VisionEngine()

    def screenshot(self) -> np.ndarray:
        index = min(self.frame_index, len(self.frames) - 1)
        self.frame_index += 1
        return self.frames[index]

    def tap(self, x: int | None = None, y: int | None = None) -> None:
        assert x is not None and y is not None
        self.actions.append(("tap", (x, y)))

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.actions.append(("point", (x, y)))

    def wait(self, ms: int | float) -> None:
        return None

    def wake_from_power_saving_if_needed(self) -> bool:
        return False

    def collapse_chat_if_open(self, wait_after_click_ms: int = 800) -> bool:
        return False

    def collapse_emotion_panel_if_open(self, **kwargs) -> bool:
        return False

    def _log(self, message: str) -> None:
        self.logs.append(message)

    def save_debug_screenshot(self, prefix: str = "debug") -> str:
        return f"{prefix}.png"


LOGIN_FIXTURES = Path(__file__).parent / "fixtures" / "ymjh" / "login_startup"


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


def test_calendar_preparation_runs_once_during_close_candidate_loop() -> None:
    first = np.zeros((720, 1280, 3), dtype=np.uint8)
    second = np.full_like(first, 180)
    final = np.full_like(first, 40)
    close = make_match((1200, 50), 0.97)
    task = CloseTask(
        [first, second, final, final],
        {id(first): [close], id(second): [close], id(final): []},
    )

    task.close_all_panels(timeout_ms=0)

    assert task.calendar_prepare_calls == 1


def test_calendar_cleanup_clicks_page_reward_before_close_icon() -> None:
    dirty = load_image(LOGIN_FIXTURES / "dirty_main_calendar_detail_power_saving.webp")
    clear = load_image(LOGIN_FIXTURES / "dirty_main_calendar_clear_power_saving.webp")
    main = np.zeros_like(clear)
    task = RealCalendarCloseTask([dirty, clear, clear, main])

    task.close_all_panels(timeout_ms=0)

    assert YmGameTask.POINT_JIANGHU_CALENDAR_PAGE_REWARD == (322, 568)
    assert task.actions == [
        ("point", YmGameTask.POINT_JIANGHU_CALENDAR_PAGE_REWARD),
        ("tap", (1163, 56)),
    ]
    assert task.logs.index(
        "检测到江湖日历，先点击一次“本页奖励”四字入口关闭详情遮挡"
    ) < task.logs.index("本页奖励遮挡清理完成，通用关闭按钮复核通过")


def test_calendar_without_detail_still_clicks_page_reward_once() -> None:
    clear = load_image(LOGIN_FIXTURES / "dirty_main_calendar_clear_power_saving.webp")
    main = np.zeros_like(clear)
    task = RealCalendarCloseTask([clear, clear, clear, main])

    task.close_all_panels(timeout_ms=0)

    assert task.actions.count(
        ("point", YmGameTask.POINT_JIANGHU_CALENDAR_PAGE_REWARD)
    ) == 1
    assert task.actions[-1] == ("tap", (1163, 56))


def test_calendar_missing_close_icon_stops_after_reward_click() -> None:
    dirty = load_image(LOGIN_FIXTURES / "dirty_main_calendar_detail_power_saving.webp")
    without_close = load_image(
        LOGIN_FIXTURES / "dirty_main_calendar_clear_power_saving.webp"
    )
    x, y, width, height = YmGameTask.ROI_JIANGHU_CALENDAR_CLOSE
    without_close[y : y + height, x : x + width] = 0
    task = RealCalendarCloseTask([dirty, without_close])

    with pytest.raises(RuntimeError, match="未识别到通用关闭按钮"):
        task.close_all_panels(timeout_ms=0)

    assert task.actions == [
        ("point", YmGameTask.POINT_JIANGHU_CALENDAR_PAGE_REWARD)
    ]


def test_calendar_marker_and_general_close_templates_match_real_frames_strictly() -> None:
    vision = VisionEngine()
    dirty = load_image(LOGIN_FIXTURES / "dirty_main_calendar_detail_power_saving.webp")
    clear = load_image(LOGIN_FIXTURES / "dirty_main_calendar_clear_power_saving.webp")

    marker = vision.match_template(
        dirty,
        YmGameTask.TEXT_JIANGHU_CALENDAR,
        threshold=YmGameTask.JIANGHU_CALENDAR_MARKER_THRESHOLD,
        roi=YmGameTask.ROI_JIANGHU_CALENDAR_MARKER,
    )
    obstructed_close = vision.match_template(
        dirty,
        YmGameTask.GENERAL_CLOSE_TEMPLATES,
        threshold=YmGameTask.CLOSE_MATCH_THRESHOLD,
        roi=YmGameTask.ROI_JIANGHU_CALENDAR_CLOSE,
    )
    visible_close = vision.match_template(
        clear,
        YmGameTask.GENERAL_CLOSE_TEMPLATES,
        threshold=YmGameTask.CLOSE_MATCH_THRESHOLD,
        roi=YmGameTask.ROI_JIANGHU_CALENDAR_CLOSE,
    )

    assert marker.found and marker.score >= 0.95
    assert not obstructed_close.found
    assert visible_close.found and visible_close.score >= 0.95
