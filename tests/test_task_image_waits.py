from __future__ import annotations

import pytest

import botCore.task as task_module
from botCore import GameTask, StepStopException


def test_wait_image_appear_uses_find_image_without_roi(monkeypatch) -> None:
    task = GameTask()
    calls: list[tuple[object, float, object]] = []
    callbacks: list[bool] = []

    def find_image(template, threshold=0.8, roi=None) -> bool:
        calls.append((template, threshold, roi))
        task._last_match_center = (120, 240)
        return True

    tapped: list[tuple[int | None, int | None]] = []
    monkeypatch.setattr(task, "find_image", find_image)
    monkeypatch.setattr(task, "tap", lambda x=None, y=None: tapped.append((x, y)))

    assert task.wait_image_appear(
        ["primary.png", "fallback.png"],
        threshold=0.9,
        callback=callbacks.append,
    )
    assert calls == [(["primary.png", "fallback.png"], 0.9, None)]
    assert callbacks == [True]

    task.click(offset=0)
    assert tapped == [(120, 240)]


def test_wait_image_appear_passes_roi_to_every_find_attempt(monkeypatch) -> None:
    task = GameTask()
    roi = (900, 500, 300, 200)
    outcomes = iter((False, False, True))
    calls: list[tuple[object, float, object]] = []
    waits: list[int | float] = []
    callbacks: list[bool] = []

    def find_image(template, threshold=0.8, roi=None) -> bool:
        calls.append((template, threshold, roi))
        return next(outcomes)

    monkeypatch.setattr(task, "find_image", find_image)
    monkeypatch.setattr(task, "wait", waits.append)

    assert task.wait_image_appear(
        "button.png",
        timeout_ms=None,
        threshold=0.92,
        callback=callbacks.append,
        interval_ms=125,
        roi=roi,
    )
    assert calls == [("button.png", 0.92, roi)] * 3
    assert waits == [125, 125]
    assert callbacks == [False, False, True]


def test_wait_image_appear_timeout_preserves_callback_behavior(monkeypatch) -> None:
    task = GameTask()
    clock = iter((0.0, 0.0, 0.1, 0.1))
    callbacks: list[bool] = []
    calls: list[tuple[object, float, object]] = []

    monkeypatch.setattr(task_module.time, "perf_counter", lambda: next(clock))

    def find_image(template, threshold=0.8, roi=None) -> bool:
        calls.append((template, threshold, roi))
        return False

    monkeypatch.setattr(task, "find_image", find_image)

    assert not task.wait_image_appear(
        "missing.png",
        timeout_ms=100,
        callback=callbacks.append,
        roi=(0, 0, 100, 100),
    )
    assert calls == [("missing.png", 0.8, (0, 0, 100, 100))]
    assert callbacks == [False, False]
    assert task._last_match_center is None


def test_wait_image_appear_honors_stop_before_finding(monkeypatch) -> None:
    task = GameTask()
    task.stop()
    monkeypatch.setattr(
        task,
        "find_image",
        lambda *_args, **_kwargs: pytest.fail("停止后不应继续找图"),
    )

    with pytest.raises(StepStopException, match="Stop requested"):
        task.wait_image_appear("button.png", timeout_ms=None)
