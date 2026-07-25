from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

import ymjh_bot.ym_game_task as ym_game_task_module
from ymjh_bot.ym_game_task import YmGameTask


FIXTURES = Path(__file__).parent / "fixtures" / "ymjh"


def load_fixture(name: str) -> np.ndarray:
    image = cv2.imread(str(FIXTURES / name), cv2.IMREAD_COLOR)
    assert image is not None
    return image


class HealthRecoveryTask(YmGameTask):
    def __init__(
        self,
        health_ratio: float | None,
        *,
        main_scene_visible: bool = True,
        detection_error: Exception | None = None,
        meditate_found: bool = True,
        wait_full_result: bool = True,
        wait_full_error: Exception | None = None,
        post_meditation_wait_error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.health_ratio = health_ratio
        self.main_scene_visible = main_scene_visible
        self.detection_error = detection_error
        self.meditate_found = meditate_found
        self.wait_full_result = wait_full_result
        self.wait_full_error = wait_full_error
        self.post_meditation_wait_error = post_meditation_wait_error
        self.post_meditation_wait_raised = False
        self.meditation_click_completed = False
        self.detect_calls = 0
        self.wait_health_full_calls = 0
        self.actions: list[tuple] = []
        self.template_calls: list[tuple] = []
        self.logs: list[str] = []

    def collapse_chat_if_open(self, wait_after_click_ms: int = 800) -> bool:
        return False

    def find_image(self, template, threshold=0.8, roi=None) -> bool:
        assert template == self.BTN_BIAOQING
        return self.main_scene_visible

    def detect_health_ratio(self) -> float | None:
        self.detect_calls += 1
        if self.detection_error is not None:
            raise self.detection_error
        return self.health_ratio

    def click(self, offset: int = 3) -> None:
        self.actions.append(("click", offset))

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.actions.append(("point", x, y, offset))

    def click_template_if_available(
        self,
        template,
        *,
        timeout_ms=3000,
        description,
        threshold=0.8,
        roi=None,
        wait_after_click_ms=1000,
    ) -> bool:
        self.template_calls.append(
            (
                template,
                timeout_ms,
                description,
                threshold,
                roi,
                wait_after_click_ms,
            )
        )
        self.meditation_click_completed = self.meditate_found
        return self.meditate_found

    def wait_health_full(self) -> bool:
        self.wait_health_full_calls += 1
        if self.wait_full_error is not None:
            raise self.wait_full_error
        return self.wait_full_result

    def wait(self, ms: int | float) -> None:
        if (
            self.post_meditation_wait_error is not None
            and self.meditation_click_completed
            and ms == 1000
            and not self.post_meditation_wait_raised
        ):
            self.post_meditation_wait_raised = True
            raise self.post_meditation_wait_error

    def _log(self, message: str) -> None:
        self.logs.append(message)


class HealthScreenshotTask(YmGameTask):
    def __init__(self, screenshot: np.ndarray | None) -> None:
        super().__init__()
        self._screenshot = screenshot

    def screenshot(self) -> np.ndarray | None:
        return self._screenshot


class HealthFullPollingTask(YmGameTask):
    def __init__(self, health_ratios: list[float | None]) -> None:
        super().__init__()
        self.health_ratios = health_ratios
        self.wait_calls: list[int | float] = []
        self.logs: list[str] = []

    def detect_health_ratio(self) -> float | None:
        return self.health_ratios.pop(0)

    def wait(self, ms: int | float) -> None:
        self.wait_calls.append(ms)

    def _log(self, message: str) -> None:
        self.logs.append(message)


class FakeClock:
    def __init__(self) -> None:
        self.current = 100.0

    def __call__(self) -> float:
        return self.current

    def advance(self, ms: int | float) -> None:
        self.current += ms / 1000.0


class HealthDurationFallbackTask(YmGameTask):
    def __init__(self, health_ratio: float | None, clock: FakeClock) -> None:
        super().__init__()
        self.health_ratio = health_ratio
        self.clock = clock
        self.detect_calls = 0
        self.wait_calls: list[int | float] = []
        self.logs: list[str] = []

    def detect_health_ratio(self) -> float | None:
        self.detect_calls += 1
        return self.health_ratio

    def wait(self, ms: int | float) -> None:
        self.wait_calls.append(ms)
        self.clock.advance(ms)

    def _log(self, message: str) -> None:
        self.logs.append(message)


class TimedFallbackRecoveryTask(HealthRecoveryTask):
    def __init__(self, health_ratio: float | None, clock: FakeClock) -> None:
        super().__init__(health_ratio)
        self.clock = clock
        self.poll_started_elapsed_ms: float | None = None
        self.recover_elapsed_ms: float | None = None

    def wait(self, ms: int | float) -> None:
        self.clock.advance(ms)

    def wait_health_full(self) -> bool:
        self.wait_health_full_calls += 1
        assert self._health_recover_started_at is not None
        self.poll_started_elapsed_ms = (
            self.clock() - self._health_recover_started_at
        ) * 1000
        result = YmGameTask.wait_health_full(self)
        self.recover_elapsed_ms = (
            self.clock() - self._health_recover_started_at
        ) * 1000
        return result


class HealthPollingDetectionErrorTask(HealthRecoveryTask):
    def __init__(self) -> None:
        super().__init__(None)

    def detect_health_ratio(self) -> float | None:
        self.detect_calls += 1
        if self.detect_calls == 1:
            return None
        raise RuntimeError("poll detection failed")

    def wait_health_full(self) -> bool:
        self.wait_health_full_calls += 1
        return YmGameTask.wait_health_full(self)


def test_unrecognized_health_recovers_after_main_scene_is_confirmed() -> None:
    task = HealthRecoveryTask(None)

    task.recover_health_if_needed()

    assert task.detect_calls == 1
    assert task.wait_health_full_calls == 1
    assert task.template_calls == [
        (
            task.BTN_EMOTION_MEDITATE,
            3000,
            "打坐表情",
            task.EMOTION_MEDITATE_THRESHOLD,
            task.ROI_EMOTION_PANEL,
            0,
        )
    ]
    assert task.actions == [
        ("click", 0),
        ("point", task.POINT_EMOTION_SINGLE_TAB[0], task.POINT_EMOTION_SINGLE_TAB[1], 0),
        ("point", task.POINT_EMOTION_COLLAPSE[0], task.POINT_EMOTION_COLLAPSE[1], 0),
        ("point", task.POINT_LIGHTNESS[0], task.POINT_LIGHTNESS[1], 0),
    ]
    assert "血量无法识别，按低血量处理，开始打坐恢复" in task.logs
    assert task._recovering_health is False


def test_unrecognized_health_does_not_recover_outside_main_scene() -> None:
    task = HealthRecoveryTask(None, main_scene_visible=False)

    task.recover_health_if_needed()

    assert task.detect_calls == 0
    assert task.wait_health_full_calls == 0
    assert task.actions == []
    assert task.logs == ["未找到主界面表情按钮，跳过自动打坐"]


def test_health_at_recovery_threshold_does_not_recover() -> None:
    task = HealthRecoveryTask(YmGameTask.HEALTH_RECOVER_THRESHOLD)

    task.recover_health_if_needed()

    assert task.detect_calls == 1
    assert task.wait_health_full_calls == 0
    assert task.actions == []


def test_fixed_health_region_reads_low_health_fixture() -> None:
    task = HealthScreenshotTask(load_fixture("1.webp"))

    health_ratio = task.detect_health_ratio()

    assert health_ratio == pytest.approx(201 / task.HEALTH_FULL_WIDTH)
    assert health_ratio < task.HEALTH_RECOVER_THRESHOLD


def test_fixed_health_region_reads_full_health_without_anchor_matching() -> None:
    task = HealthScreenshotTask(load_fixture("5.webp"))

    health_ratio = task.detect_health_ratio()

    assert health_ratio == pytest.approx(231 / task.HEALTH_FULL_WIDTH)
    assert health_ratio >= task.HEALTH_FULL_THRESHOLD
    assert not hasattr(task, "_vision")


@pytest.mark.parametrize(
    "screenshot",
    [
        np.zeros((720, 1280, 3), dtype=np.uint8),
        np.zeros((46, 333, 3), dtype=np.uint8),
        np.zeros((720, 1280), dtype=np.uint8),
        None,
    ],
)
def test_fixed_health_region_returns_none_when_it_cannot_be_read(
    screenshot: np.ndarray | None,
) -> None:
    task = HealthScreenshotTask(screenshot)

    assert task.detect_health_ratio() is None


def test_recognized_low_health_still_recovers() -> None:
    task = HealthRecoveryTask(YmGameTask.HEALTH_RECOVER_THRESHOLD - 0.01)

    task.recover_health_if_needed()

    assert task.wait_health_full_calls == 1
    assert "检测到血量较低：79.0%，开始打坐恢复" in task.logs


def test_health_detection_error_still_skips_recovery() -> None:
    task = HealthRecoveryTask(None, detection_error=RuntimeError("screenshot failed"))

    task.recover_health_if_needed()

    assert task.wait_health_full_calls == 0
    assert task.actions == []
    assert task.logs == ["血量检测失败，跳过自动打坐：screenshot failed"]


@pytest.mark.parametrize(
    ("task", "expected_error"),
    [
        (
            HealthRecoveryTask(None, wait_full_result=False),
            "打坐回血未正常完成",
        ),
        (
            HealthRecoveryTask(None, wait_full_error=RuntimeError("poll failed")),
            "poll failed",
        ),
        (
            HealthRecoveryTask(
                None,
                post_meditation_wait_error=RuntimeError("interrupted"),
            ),
            "interrupted",
        ),
    ],
)
def test_started_meditation_is_always_stopped_on_failure(
    task: HealthRecoveryTask,
    expected_error: str,
) -> None:
    with pytest.raises(RuntimeError, match=expected_error):
        task.recover_health_if_needed()

    assert task.actions[-2:] == [
        ("point", task.POINT_EMOTION_COLLAPSE[0], task.POINT_EMOTION_COLLAPSE[1], 0),
        ("point", task.POINT_LIGHTNESS[0], task.POINT_LIGHTNESS[1], 0),
    ]
    assert task._recovering_health is False
    assert task._health_recover_started_at is None


def test_polling_detection_error_is_not_treated_as_duration_fallback() -> None:
    task = HealthPollingDetectionErrorTask()

    with pytest.raises(RuntimeError, match="poll detection failed"):
        task.recover_health_if_needed()

    assert task.actions[-2:] == [
        ("point", task.POINT_EMOTION_COLLAPSE[0], task.POINT_EMOTION_COLLAPSE[1], 0),
        ("point", task.POINT_LIGHTNESS[0], task.POINT_LIGHTNESS[1], 0),
    ]
    assert "打坐已满90秒，按回满处理" not in task.logs
    assert task._recovering_health is False
    assert task._health_recover_started_at is None


def test_missing_meditation_button_does_not_run_exit_actions() -> None:
    task = HealthRecoveryTask(None, meditate_found=False)

    with pytest.raises(RuntimeError, match="未找到打坐表情"):
        task.recover_health_if_needed()

    assert task.wait_health_full_calls == 0
    assert task.actions == [
        ("click", 0),
        ("point", task.POINT_EMOTION_SINGLE_TAB[0], task.POINT_EMOTION_SINGLE_TAB[1], 0),
    ]
    assert task._recovering_health is False


def test_wait_health_full_keeps_polling_when_health_is_unrecognized() -> None:
    task = HealthFullPollingTask([None, None, YmGameTask.HEALTH_FULL_THRESHOLD])

    assert task.wait_health_full() is True
    assert task.wait_calls == [
        task.HEALTH_RECOVER_POLL_INTERVAL_MS,
        task.HEALTH_RECOVER_POLL_INTERVAL_MS,
    ]
    assert task.logs == ["打坐回血中：连续 1 次无法识别血量"]


def test_wait_health_full_keeps_polling_below_80_percent() -> None:
    task = HealthFullPollingTask([0.79, 0.80])

    assert task.wait_health_full() is True
    assert task.wait_calls == [task.HEALTH_RECOVER_POLL_INTERVAL_MS]
    assert task.logs == ["打坐回血中：79.0%"]


def test_wait_health_full_rate_limits_unrecognized_health_logs() -> None:
    task = HealthFullPollingTask(
        [None] * YmGameTask.HEALTH_UNRECOGNIZED_LOG_INTERVAL
        + [YmGameTask.HEALTH_FULL_THRESHOLD]
    )

    assert task.wait_health_full() is True
    assert len(task.wait_calls) == task.HEALTH_UNRECOGNIZED_LOG_INTERVAL
    assert task.logs == [
        "打坐回血中：连续 1 次无法识别血量",
        f"打坐回血中：连续 {task.HEALTH_UNRECOGNIZED_LOG_INTERVAL} 次无法识别血量",
    ]


@pytest.mark.parametrize("health_ratio", [0.80, 0.81, 231 / YmGameTask.HEALTH_FULL_WIDTH])
def test_wait_health_full_accepts_80_percent_or_higher(
    health_ratio: float,
) -> None:
    task = HealthFullPollingTask([health_ratio])

    assert task.wait_health_full() is True
    assert task.wait_calls == []
    assert task.logs == []


@pytest.mark.parametrize("health_ratio", [0.79, None])
def test_wait_health_full_uses_90_second_duration_fallback(
    health_ratio: float | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    monkeypatch.setattr(
        ym_game_task_module,
        "time",
        SimpleNamespace(perf_counter=clock),
    )
    task = HealthDurationFallbackTask(health_ratio, clock)

    assert task.wait_health_full() is True
    assert sum(task.wait_calls) == task.HEALTH_RECOVER_FALLBACK_MS
    assert task.logs[-1] == "打坐已满90秒，按回满处理"


def test_recovery_duration_starts_when_meditation_click_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    monkeypatch.setattr(
        ym_game_task_module,
        "time",
        SimpleNamespace(perf_counter=clock),
    )
    task = TimedFallbackRecoveryTask(None, clock)

    task.recover_health_if_needed()

    assert task.poll_started_elapsed_ms == pytest.approx(1000)
    assert task.recover_elapsed_ms == pytest.approx(task.HEALTH_RECOVER_FALLBACK_MS)
    assert "打坐已满90秒，按回满处理" in task.logs
    assert task.logs[-1] == "血量已回满，退出打坐"
    assert task.actions[-2:] == [
        ("point", task.POINT_EMOTION_COLLAPSE[0], task.POINT_EMOTION_COLLAPSE[1], 0),
        ("point", task.POINT_LIGHTNESS[0], task.POINT_LIGHTNESS[1], 0),
    ]
    assert task._recovering_health is False
    assert task._health_recover_started_at is None
