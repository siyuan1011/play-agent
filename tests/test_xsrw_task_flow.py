from __future__ import annotations

import numpy as np

from ymjh_bot.task.XSRW_task import BountyCardSnapshot, BountyPanelSnapshot, XSRWTask


def _snapshot(*, daily_complete: bool = False) -> BountyPanelSnapshot:
    return BountyPanelSnapshot(
        screenshot=np.zeros((720, 1280, 3), dtype=np.uint8),
        visible=True,
        daily_complete=daily_complete,
    )


def test_bounty_flow_has_no_overall_timeout() -> None:
    assert XSRWTask.run_bounty_flow._step_meta["timeout_ms"] is None


def test_no_eligible_bounty_refreshes_until_daily_limit_without_failure() -> None:
    task = XSRWTask()
    initial = _snapshot()
    complete = _snapshot(daily_complete=True)
    refresh_inputs: list[BountyPanelSnapshot] = []
    logs: list[str] = []

    task.is_stopped = lambda: False  # type: ignore[method-assign]
    task.refresh_bounty_panel = lambda snapshot: (  # type: ignore[method-assign]
        refresh_inputs.append(snapshot) or complete
    )
    task._log = logs.append  # type: ignore[method-assign]

    result = task.acquire_bounty_round(initial)

    assert result is complete
    assert refresh_inputs == [initial]
    assert not any("盒子 100" in message for message in logs)


def test_unconfirmed_accept_refreshes_instead_of_failing_the_task() -> None:
    task = XSRWTask()
    card = BountyCardSnapshot(
        slot_index=0,
        category="聚义平冤",
        reward_glyph_count=4,
        reward_eligible=True,
        action="接取",
        action_center=(367, 508),
    )
    initial = BountyPanelSnapshot(
        screenshot=np.zeros((720, 1280, 3), dtype=np.uint8),
        visible=True,
        daily_complete=False,
        cards=(card,),
    )
    accepted = _snapshot(daily_complete=True)
    no_eligible = _snapshot()
    refresh_inputs: list[BountyPanelSnapshot] = []

    task.is_stopped = lambda: False  # type: ignore[method-assign]
    task.attempt_accept_bounty = lambda _snapshot, _card: (  # type: ignore[method-assign]
        False,
        no_eligible,
    )
    task.refresh_bounty_panel = lambda snapshot: (  # type: ignore[method-assign]
        refresh_inputs.append(snapshot) or accepted
    )
    task._log = lambda _message: None  # type: ignore[method-assign]

    result = task.acquire_bounty_round(initial)

    assert result is accepted
    assert refresh_inputs == [no_eligible]
