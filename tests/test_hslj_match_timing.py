from __future__ import annotations

import importlib

from ymjh_bot.task.HSLJ_task import HSLJTask


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def perf_counter(self) -> float:
        return self.now

    def advance(self, milliseconds: int | float) -> None:
        self.now += float(milliseconds) / 1000.0


class TimingHSLJTask(HSLJTask):
    def __init__(self, clock: FakeClock, *, ready_at: float | None = None) -> None:
        super().__init__()
        self.clock = clock
        self.ready_at = ready_at
        self.waits: list[int] = []
        self.click_times: list[float] = []
        self.cancel_times: list[float] = []
        self.debug_times: list[float] = []

    def wait(self, ms: int | float) -> None:
        self.waits.append(int(ms))
        self.clock.advance(ms)

    def confirm_match_leave_team_dialog_if_needed(self, activity_name: str, **kwargs) -> bool:
        return False

    def is_ready_button_visible(self) -> bool:
        return self.ready_at is not None and self.clock.now >= self.ready_at

    def is_result_panel_visible_quiet(self) -> bool:
        return False

    def is_match_success_visible_quiet(self) -> bool:
        return False

    def is_hslj_panel_visible_quiet(self) -> bool:
        return False

    def click(self, offset: int = 3) -> None:
        self.click_times.append(self.clock.now)

    def save_debug_screenshot(self, prefix: str) -> str:
        return f"{prefix}.png"

    def cancel_current_match(self, mode: str, match_index: int) -> bool:
        self.cancel_times.append(self.clock.now)
        return True

    def _log(self, message: str) -> None:
        return None

    def _debug(self, message: str) -> None:
        self.debug_times.append(self.clock.now)


def patch_match_clocks(monkeypatch, clock: FakeClock) -> None:
    hslj_module = importlib.import_module("ymjh_bot.task.HSLJ_task")
    ym_task_module = importlib.import_module("ymjh_bot.ym_game_task")
    monkeypatch.setattr(hslj_module.time, "perf_counter", clock.perf_counter)
    monkeypatch.setattr(ym_task_module.time, "perf_counter", clock.perf_counter)


def test_hslj_match_wait_constants() -> None:
    assert HSLJTask.READY_TIMEOUT_MS == 300_000
    assert HSLJTask.MATCH_READY_TIMEOUT_MS == 300_000
    assert HSLJTask.MATCH_WAIT_POLL_INTERVAL_MS == 3_000
    assert HSLJTask.MATCH_WAIT_HEARTBEAT_MS == 10_000
    assert HSLJTask.SINGLE_MATCH_TIMEOUT_MS == 480_000
    assert HSLJTask.RESULT_TIMEOUT_MS == 420_000


def test_hslj_match_cancels_only_after_one_hundred_three_second_polls(monkeypatch) -> None:
    clock = FakeClock()
    patch_match_clocks(monkeypatch, clock)
    task = TimingHSLJTask(clock)

    result = task.click_ready_button(task.MODE_3V3, 1)

    assert result == task.BATTLE_FINISH_RETURNED_PANEL
    assert task.waits == [3_000] * 100
    assert task.cancel_times == [400.0]
    assert task.debug_times[:3] == [100.0, 112.0, 124.0]


def test_hslj_ready_is_clicked_on_next_three_second_poll(monkeypatch) -> None:
    clock = FakeClock()
    patch_match_clocks(monkeypatch, clock)
    task = TimingHSLJTask(clock, ready_at=104.0)

    result = task.click_ready_button(task.MODE_1V1, 1)

    assert result == task.MATCH_READY_STATE_READY
    assert task.click_times == [106.0]
    assert task.waits == [3_000, 3_000, 1_000]
    assert task.cancel_times == []
