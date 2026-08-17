from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from botCore import ImageMatchResult, VisionEngine, load_task_class
from ymjh_bot.run_queue import _load_available_tasks
from ymjh_bot.task.JYPY_task import JYPYTask
from ymjh_bot.task.XSRW_task import (
    BountyCardSnapshot,
    BountyPanelSnapshot,
    XSRWTask,
)


FIXTURES = Path(__file__).parent / "fixtures" / "ymjh" / "xsrw"


def load_image(name: str) -> np.ndarray:
    image = cv2.imread(str(FIXTURES / name), cv2.IMREAD_COLOR)
    assert image is not None, name
    return image


def make_card(
    slot_index: int,
    *,
    category: str | None = "聚义平冤",
    action: str = "接取",
    reward_eligible: bool = True,
) -> BountyCardSnapshot:
    return BountyCardSnapshot(
        slot_index=slot_index,
        category=category,  # type: ignore[arg-type]
        reward_glyph_count=4 if reward_eligible else 3,
        reward_eligible=reward_eligible,
        action=action,  # type: ignore[arg-type]
        action_center=(300 + slot_index * 220, 508) if action != "未知" else None,
    )


def make_snapshot(
    *cards: BountyCardSnapshot,
    daily_complete: bool = False,
) -> BountyPanelSnapshot:
    return BountyPanelSnapshot(
        screenshot=np.full((720, 1280, 3), 255, dtype=np.uint8),
        visible=True,
        daily_complete=daily_complete,
        cards=tuple(cards),
    )


def test_xsrw_templates_are_packaged() -> None:
    templates = [
        XSRWTask.ICON_BOUNTY,
        XSRWTask.TEXT_PANEL_TITLE,
        XSRWTask.BTN_REFRESH,
        XSRWTask.BTN_ACCEPT,
        XSRWTask.BTN_FORWARD,
        XSRWTask.TEXT_DEPOSIT_NOTICE,
        XSRWTask.TEXT_CATEGORY_JYPY,
        XSRWTask.TEXT_CATEGORY_JHJS,
        XSRWTask.TEXT_CHALLENGE_VICTORY,
        XSRWTask.TEXT_DAILY_PANEL_TITLE,
        XSRWTask.BTN_DAILY_CHALLENGE,
        XSRWTask.BTN_DAILY_CONFIRM,
        XSRWTask.BTN_DAILY_FIND_TEAM,
        XSRWTask.TEXT_DAILY_TEAM_LIST,
        XSRWTask.BTN_DAILY_JOIN_TEAM,
        XSRWTask.BTN_DAILY_TEAM_REFRESH,
        XSRWTask.BTN_DAILY_EXIT_SOLO,
    ]

    assert all(Path(template).is_file() for template in templates)


def test_bounty_entry_matches_real_activity_screenshot() -> None:
    match = VisionEngine().match_binary_template(
        load_image("activity.webp"),
        XSRWTask.ICON_BOUNTY,
        mode="light_foreground",
        threshold=XSRWTask.ENTRY_THRESHOLD,
        roi=XSRWTask.ROI_BOUNTY_ENTRY,
    )

    assert match.found
    assert match.score >= 0.99
    assert match.center == (1113, 51)


def test_jypy_victory_template_matches_only_the_challenge_result() -> None:
    vision = VisionEngine()
    match = vision.match_template(
        load_image("jypy_victory.webp"),
        XSRWTask.TEXT_CHALLENGE_VICTORY,
        threshold=XSRWTask.CHALLENGE_VICTORY_THRESHOLD,
        roi=XSRWTask.ROI_CHALLENGE_VICTORY,
    )
    panel_match = vision.match_template(
        load_image("panel_live_translucent.webp"),
        XSRWTask.TEXT_CHALLENGE_VICTORY,
        threshold=XSRWTask.CHALLENGE_VICTORY_THRESHOLD,
        roi=XSRWTask.ROI_CHALLENGE_VICTORY,
    )

    assert match.found
    assert match.score >= 0.99
    assert match.center == (640, 187)
    assert not panel_match.found


def test_daily_bounty_entry_templates_match_real_device_states() -> None:
    vision = VisionEngine()
    panel = load_image("daily_panel.webp")
    confirm = load_image("daily_confirm.webp")

    title_match = vision.match_binary_template(
        panel,
        XSRWTask.TEXT_DAILY_PANEL_TITLE,
        mode="light_foreground",
        threshold=XSRWTask.DAILY_PANEL_THRESHOLD,
        roi=XSRWTask.ROI_DAILY_PANEL_TITLE,
    )
    challenge_match = vision.match_binary_template(
        panel,
        XSRWTask.BTN_DAILY_CHALLENGE,
        mode="otsu_dark",
        threshold=XSRWTask.DAILY_CHALLENGE_THRESHOLD,
        roi=XSRWTask.ROI_DAILY_CHALLENGE,
    )
    confirm_match = vision.match_binary_template(
        confirm,
        XSRWTask.BTN_DAILY_CONFIRM,
        mode="otsu_dark",
        threshold=XSRWTask.DAILY_CONFIRM_THRESHOLD,
        roi=XSRWTask.ROI_DAILY_CONFIRM,
    )

    assert title_match.found and title_match.center == (122, 30)
    assert challenge_match.found and challenge_match.center == (1165, 660)
    assert confirm_match.found and confirm_match.center == (1067, 597)


def test_daily_team_templates_match_real_device_state() -> None:
    vision = VisionEngine()
    team_list = load_image("daily_team_list.webp")

    title_match = vision.match_binary_template(
        team_list,
        XSRWTask.TEXT_DAILY_TEAM_LIST,
        mode="light_foreground",
        threshold=XSRWTask.DAILY_TEAM_THRESHOLD,
        roi=XSRWTask.ROI_DAILY_TEAM_LIST,
    )
    refresh_match = vision.match_binary_template(
        team_list,
        XSRWTask.BTN_DAILY_TEAM_REFRESH,
        mode="otsu_dark",
        threshold=XSRWTask.DAILY_TEAM_THRESHOLD,
        roi=XSRWTask.ROI_DAILY_TEAM_REFRESH,
    )
    join_matches = vision.match_all_templates(
        team_list,
        XSRWTask.BTN_DAILY_JOIN_TEAM,
        threshold=XSRWTask.DAILY_JOIN_THRESHOLD,
        roi=XSRWTask.ROI_DAILY_JOIN_ACTIONS,
    )

    assert title_match.found and title_match.center == (830, 32)
    assert refresh_match.found and refresh_match.center == (1205, 689)
    assert [match.center for match in join_matches[:3]] == [
        (1216, 154),
        (1216, 304),
        (1216, 454),
    ]


def test_daily_solo_exit_template_matches_real_device_state() -> None:
    match = VisionEngine().match_template(
        load_image("daily_solo_exit.webp"),
        XSRWTask.BTN_DAILY_EXIT_SOLO,
        threshold=XSRWTask.DAILY_SOLO_EXIT_THRESHOLD,
        roi=XSRWTask.ROI_DAILY_EXIT_SOLO,
    )

    assert match.found
    assert match.score >= 0.99
    assert match.center == (855, 508)


def test_deposit_notice_template_matches_real_device_state() -> None:
    match = VisionEngine().match_binary_template(
        load_image("deposit_modal.webp"),
        XSRWTask.TEXT_DEPOSIT_NOTICE,
        mode="light_foreground",
        threshold=XSRWTask.DEPOSIT_NOTICE_THRESHOLD,
        roi=XSRWTask.ROI_DEPOSIT_NOTICE,
    )

    assert match.found
    assert match.score >= 0.99


@pytest.mark.parametrize(
    ("fixture_name", "expected"),
    [
        (
            "panel_available.webp",
                [
                    ("聚义平冤", "接取"),
                    ("聚义平冤", "接取"),
                    ("聚义平冤", "接取"),
                    ("聚义平冤", "接取"),
                ],
            ),
        (
            "panel_accepted.webp",
                [
                    ("聚义平冤", "前往"),
                    ("聚义平冤", "接取"),
                    ("聚义平冤", "接取"),
                    ("聚义平冤", "接取"),
                ],
            ),
        (
            "panel_mixed.webp",
                [
                    ("聚义平冤", "前往"),
                    ("江湖纪事", "接取"),
                    ("江湖纪事", "接取"),
                    ("江湖纪事", "接取"),
                ],
            ),
        (
            "panel_live_translucent.webp",
                [
                    ("聚义平冤", "前往"),
                    ("江湖纪事", "前往"),
                    ("江湖纪事", "接取"),
                    ("江湖纪事", "接取"),
                ],
            ),
    ],
)
def test_real_bounty_panels_classify_cards_without_ocr(
    fixture_name: str,
    expected: list[tuple[str, str]],
) -> None:
    task = XSRWTask()
    task._vision = VisionEngine()

    snapshot = task.read_bounty_panel(load_image(fixture_name))

    assert snapshot.visible
    assert not snapshot.daily_complete
    assert [
        (card.category, card.action)
        for card in snapshot.cards
    ] == expected
    assert all(card.reward_eligible for card in snapshot.cards)


def draw_glyph_runs(
    image: np.ndarray,
    roi: tuple[int, int, int, int],
    count: int,
    *,
    color: tuple[int, int, int] = (0, 0, 0),
    start_offset: int = 0,
) -> None:
    x, y, _, _ = roi
    for index in range(count):
        left = x + start_offset + index * 9
        image[y + 4 : y + 18, left : left + 5] = color


def test_reward_threshold_uses_glyph_count_not_text_recognition() -> None:
    image = np.full((80, 160, 3), 255, dtype=np.uint8)
    roi = (10, 10, 100, 30)

    draw_glyph_runs(image, roi, 3, color=(55, 70, 85), start_offset=5)
    assert XSRWTask.count_reward_glyph_runs(image, roi) == 3
    assert (
        XSRWTask.count_reward_glyph_runs(image, roi)
        < XSRWTask.MIN_ELIGIBLE_REWARD_GLYPHS
    )

    image[:] = 255
    draw_glyph_runs(image, roi, 4, color=(55, 70, 85), start_offset=5)
    assert XSRWTask.count_reward_glyph_runs(image, roi) == 4
    assert (
        XSRWTask.count_reward_glyph_runs(image, roi)
        >= XSRWTask.MIN_ELIGIBLE_REWARD_GLYPHS
    )


def test_daily_complete_requires_the_fifth_progress_glyph() -> None:
    task = XSRWTask()
    image = np.full((720, 1280, 3), 255, dtype=np.uint8)

    draw_glyph_runs(image, task.ROI_TODAY_PROGRESS, 4)
    assert not task._is_daily_complete(image)

    image[:] = 255
    draw_glyph_runs(image, task.ROI_TODAY_PROGRESS, 5)
    assert task._is_daily_complete(image)


def test_accept_attempt_refreshes_even_when_state_does_not_change(monkeypatch) -> None:
    task = XSRWTask()
    task._vision = VisionEngine()
    card = make_card(0)
    before = make_snapshot(card)
    refreshes: list[int] = []

    monkeypatch.setattr(task, "tap", lambda *args: None)
    monkeypatch.setattr(task, "wait", lambda *args: None)
    monkeypatch.setattr(task, "read_bounty_panel", lambda *args, **kwargs: before)
    monkeypatch.setattr(
        task,
        "refresh_bounty_panel",
        lambda *args, **kwargs: refreshes.append(1) or before,
    )
    monkeypatch.setattr(task, "_log", lambda *args: None)

    success, refreshed = task.attempt_accept_bounty(before, card)

    assert not success
    assert refreshed is before
    assert refreshes == [1]


def test_accept_attempt_confirms_same_slot_transition_to_forward(monkeypatch) -> None:
    task = XSRWTask()
    task._vision = VisionEngine()
    card = make_card(0)
    before = make_snapshot(card)
    accepted = make_snapshot(make_card(0, action="前往"))

    monkeypatch.setattr(task, "tap", lambda *args: None)
    monkeypatch.setattr(task, "wait", lambda *args: None)
    monkeypatch.setattr(task, "read_bounty_panel", lambda *args, **kwargs: accepted)
    monkeypatch.setattr(task, "refresh_bounty_panel", lambda *args, **kwargs: accepted)
    monkeypatch.setattr(task, "_log", lambda *args: None)

    success, refreshed = task.attempt_accept_bounty(before, card)

    assert success
    assert refreshed is accepted


def test_accept_attempt_confirms_deposit_before_refresh(monkeypatch) -> None:
    task = XSRWTask()
    task._vision = VisionEngine()
    card = make_card(0)
    before = make_snapshot(card)
    deposit = BountyPanelSnapshot(
        screenshot=load_image("deposit_modal.webp"),
        visible=False,
        daily_complete=False,
    )
    accepted = make_snapshot(make_card(0, action="前往"))
    reads = iter((deposit, accepted))
    clicks: list[tuple[int, int, int]] = []
    taps: list[tuple[int, int]] = []

    monkeypatch.setattr(task, "tap", lambda x, y: taps.append((x, y)))
    monkeypatch.setattr(
        task,
        "click_point",
        lambda x, y, *, offset: clicks.append((x, y, offset)),
    )
    monkeypatch.setattr(task, "wait", lambda *args: None)
    monkeypatch.setattr(task, "read_bounty_panel", lambda *args, **kwargs: next(reads))
    monkeypatch.setattr(task, "refresh_bounty_panel", lambda *args, **kwargs: accepted)
    monkeypatch.setattr(task, "_log", lambda *args: None)

    success, refreshed = task.attempt_accept_bounty(before, card)

    assert success
    assert refreshed is accepted
    assert taps == [card.action_center]
    assert clicks == [(855, 508, 0)]


def test_round_skips_low_reward_then_accepts_eligible_card(monkeypatch) -> None:
    task = XSRWTask()
    low = make_snapshot(make_card(0, reward_eligible=False))
    eligible_card = make_card(0)
    eligible = make_snapshot(eligible_card)
    full = make_snapshot(*(make_card(index, action="前往") for index in range(4)))
    refreshes: list[int] = []
    attempts: list[int] = []

    monkeypatch.setattr(
        task,
        "refresh_bounty_panel",
        lambda *args, **kwargs: refreshes.append(1) or eligible,
    )
    monkeypatch.setattr(
        task,
        "attempt_accept_bounty",
        lambda snapshot, card: attempts.append(card.slot_index) or (True, full),
    )
    monkeypatch.setattr(task, "_log", lambda *args: None)

    result = task.acquire_bounty_round(low)

    assert result is full
    assert refreshes == [1]
    assert attempts == [0]


def test_round_stops_after_one_last_daily_accept(monkeypatch) -> None:
    task = XSRWTask()
    available = make_snapshot(make_card(0))
    last_pending = make_snapshot(make_card(0, action="前往"), daily_complete=True)
    attempts: list[int] = []

    monkeypatch.setattr(
        task,
        "attempt_accept_bounty",
        lambda snapshot, card: attempts.append(card.slot_index) or (True, last_pending),
    )
    monkeypatch.setattr(task, "_log", lambda *args: None)

    result = task.acquire_bounty_round(available)

    assert result is last_pending
    assert attempts == [0]


def test_no_eligible_bounty_fails_after_thirty_refresh_states(monkeypatch) -> None:
    task = XSRWTask()
    low = make_snapshot(make_card(0, reward_eligible=False))
    refreshes: list[int] = []

    monkeypatch.setattr(
        task,
        "refresh_bounty_panel",
        lambda *args, **kwargs: refreshes.append(1) or low,
    )
    monkeypatch.setattr(task, "save_debug_screenshot", lambda prefix: f"{prefix}.png")
    monkeypatch.setattr(task, "_log", lambda *args: None)

    with pytest.raises(RuntimeError, match="连续 30 次刷新"):
        task.acquire_bounty_round(low)

    assert len(refreshes) == 29


def test_existing_pending_bounty_runs_before_new_acceptance(monkeypatch) -> None:
    task = XSRWTask()
    pending = make_snapshot(make_card(0, action="前往"))
    done = make_snapshot(daily_complete=True)
    executions: list[int] = []

    monkeypatch.setattr(task, "open_bounty_panel", lambda **kwargs: pending)
    monkeypatch.setattr(
        task,
        "execute_pending_bounties",
        lambda snapshot: executions.append(len(snapshot.pending_cards)) or done,
    )
    monkeypatch.setattr(
        task,
        "acquire_bounty_round",
        lambda snapshot: pytest.fail("已有待完成任务时不应继续接取"),
    )
    monkeypatch.setattr(task, "_log", lambda *args: None)

    task.run_bounty_flow()

    assert executions == [1]


def test_pending_categories_repeat_only_while_refreshed_cards_remain(monkeypatch) -> None:
    task = XSRWTask()
    mixed = make_snapshot(
        make_card(0, action="前往", category="聚义平冤"),
        make_card(1, action="前往", category="江湖纪事"),
    )
    daily_only = make_snapshot(make_card(0, action="前往", category="江湖纪事"))
    done = make_snapshot(daily_complete=True)
    refreshed = iter((daily_only, done))
    categories: list[str] = []

    monkeypatch.setattr(task, "tap", lambda *args: None)
    monkeypatch.setattr(task, "wait", lambda *args: None)
    monkeypatch.setattr(
        task,
        "_run_category_delegate",
        lambda category: categories.append(category),
    )
    monkeypatch.setattr(
        task,
        "open_bounty_panel",
        lambda **kwargs: next(refreshed),
    )
    monkeypatch.setattr(task, "_log", lambda *args: None)

    result = task.execute_pending_bounties(mixed)

    assert result is done
    assert categories == ["聚义平冤", "江湖纪事"]


def test_jypy_delegate_exits_confirmed_victory_screen(monkeypatch) -> None:
    task = XSRWTask()
    task._vision = VisionEngine()
    clicks: list[tuple[int, int, int]] = []
    waits: list[int] = []

    monkeypatch.setattr(task, "screenshot", lambda: load_image("jypy_victory.webp"))
    monkeypatch.setattr(
        task,
        "click_point",
        lambda x, y, *, offset: clicks.append((x, y, offset)),
    )
    monkeypatch.setattr(task, "wait", waits.append)
    monkeypatch.setattr(task, "_log", lambda *args: None)

    task.run_jypy_bounty_challenge()

    assert clicks == [(640, 600, 0)]
    assert waits == [task.CHALLENGE_VICTORY_EXIT_SETTLE_MS]


def test_daily_bounty_entry_clicks_challenge_then_confirm(monkeypatch) -> None:
    task = XSRWTask()
    matches = iter(
        (
            ImageMatchResult(False, 0.1, None, None),
            ImageMatchResult(True, 0.99, (122, 30), (25, 5, 220, 55)),
            ImageMatchResult(True, 0.99, (1165, 660), (1085, 625, 1245, 695)),
            ImageMatchResult(True, 0.99, (1067, 597), (975, 560, 1160, 635)),
        )
    )
    taps: list[tuple[int, int]] = []
    waits: list[int] = []

    monkeypatch.setattr(task, "_wait_binary_match", lambda *args, **kwargs: next(matches))
    monkeypatch.setattr(task, "tap", lambda x, y: taps.append((x, y)))
    monkeypatch.setattr(task, "wait", waits.append)
    monkeypatch.setattr(task, "_log", lambda *args: None)

    task.enter_daily_bounty_solo()

    assert taps == [(1165, 660), (1067, 597)]
    assert waits == [task.DAILY_ENTRY_SETTLE_MS]


def test_daily_bounty_prefers_exact_dungeon_team(monkeypatch) -> None:
    task = XSRWTask()
    task._vision = VisionEngine()
    matches = iter(
        (
            ImageMatchResult(True, 0.99, (122, 30), (25, 5, 220, 55)),
            ImageMatchResult(True, 0.99, (987, 660), (915, 625, 1059, 695)),
            ImageMatchResult(True, 1.0, (830, 32), (771, 8, 889, 56)),
        )
    )
    taps: list[tuple[int, int]] = []

    monkeypatch.setattr(task, "_wait_binary_match", lambda *args, **kwargs: next(matches))
    monkeypatch.setattr(task, "screenshot", lambda: load_image("daily_team_list.webp"))
    monkeypatch.setattr(task, "tap", lambda x, y: taps.append((x, y)))
    monkeypatch.setattr(
        task,
        "_wait_daily_team_follow_confirm",
        lambda **kwargs: True,
    )
    monkeypatch.setattr(task, "_log", lambda *args: None)

    assert task.try_join_daily_bounty_team()
    assert taps == [(987, 660), (1216, 154)]


def test_daily_bounty_applies_to_all_visible_teams_before_refresh(monkeypatch) -> None:
    task = XSRWTask()
    task._vision = VisionEngine()
    matches = iter(
        (
            ImageMatchResult(True, 0.99, (122, 30), (25, 5, 220, 55)),
            ImageMatchResult(True, 0.99, (987, 660), (915, 625, 1059, 695)),
            ImageMatchResult(True, 1.0, (830, 32), (771, 8, 889, 56)),
        )
    )
    confirm_states = iter((False, False, False, True))
    taps: list[tuple[int, int]] = []

    monkeypatch.setattr(task, "_wait_binary_match", lambda *args, **kwargs: next(matches))
    monkeypatch.setattr(task, "screenshot", lambda: load_image("daily_team_list.webp"))
    monkeypatch.setattr(task, "tap", lambda x, y: taps.append((x, y)))
    monkeypatch.setattr(
        task,
        "_wait_daily_team_follow_confirm",
        lambda **kwargs: next(confirm_states),
    )
    monkeypatch.setattr(task, "_log", lambda *args: None)

    assert task.try_join_daily_bounty_team()
    assert taps == [
        (987, 660),
        (1216, 154),
        (1216, 304),
        (1216, 454),
    ]


def test_daily_bounty_falls_back_to_solo_after_team_search(monkeypatch) -> None:
    task = XSRWTask()
    clicks: list[tuple[int, int, int]] = []
    solo_entries: list[bool] = []
    waits: list[int] = []

    monkeypatch.setattr(task, "try_join_daily_bounty_team", lambda: False)
    monkeypatch.setattr(
        task,
        "click_point",
        lambda x, y, *, offset: clicks.append((x, y, offset)),
    )
    monkeypatch.setattr(task, "enter_daily_bounty_solo", lambda: solo_entries.append(True))
    monkeypatch.setattr(task, "wait", waits.append)
    monkeypatch.setattr(task, "_log", lambda *args: None)

    joined_team = task.enter_daily_bounty_dungeon()

    assert not joined_team
    assert clicks == [(1234, 30, 0)]
    assert waits == [task.DAILY_TEAM_LIST_SETTLE_MS]
    assert solo_entries == [True]


def test_daily_bounty_solo_exit_uses_right_side_action(monkeypatch) -> None:
    task = XSRWTask()
    self_clicks: list[str] = []
    delegate_clicks: list[str] = []
    transfer_waits: list[int] = []

    class FakeDailyDelegate:
        ICON_DUNGEON_EXIT = "exit.png"
        DUNGEON_EXIT_ACTION_TIMEOUT_MS = 5000
        DUNGEON_EXIT_THRESHOLD = 0.9
        ROI_DUNGEON_EXIT = (960, 155, 85, 85)

        @staticmethod
        def click_template_if_available(template, **kwargs) -> bool:
            delegate_clicks.append(template)
            return True

        @staticmethod
        def wait_for_dungeon_transfer_complete(*, timeout_ms: int) -> None:
            transfer_waits.append(timeout_ms)

    monkeypatch.setattr(
        task,
        "click_template_if_available",
        lambda template, **kwargs: self_clicks.append(template) or True,
    )
    monkeypatch.setattr(task, "_log", lambda *args: None)

    task.leave_daily_bounty_solo(FakeDailyDelegate())  # type: ignore[arg-type]

    assert delegate_clicks == ["exit.png"]
    assert self_clicks == [task.BTN_DAILY_EXIT_SOLO]
    assert transfer_waits == [60000]


def test_daily_bounty_flow_tolerates_hidden_tracker_during_battle(monkeypatch) -> None:
    task = XSRWTask()
    transfer_states = iter((False, False, True))
    tracker_states = iter((False, True))
    waits: list[int] = []

    class FakeDailyDelegate:
        TASK_FLOW_TIMEOUT_MS = 1800000
        TASK_FLOW_RETRY_WAIT_MS = 5000

        @staticmethod
        def is_stopped() -> bool:
            return False

        @staticmethod
        def is_dungeon_transfer_out_visible() -> bool:
            return next(transfer_states)

        @staticmethod
        def click_current_dungeon_task_if_visible() -> bool:
            return next(tracker_states)

    monkeypatch.setattr(task, "wait", waits.append)
    monkeypatch.setattr(task, "_log", lambda *args: None)

    task.run_daily_bounty_raid_flow(FakeDailyDelegate())  # type: ignore[arg-type]

    assert waits == [5000]


def test_stop_propagates_to_active_delegate() -> None:
    task = XSRWTask()
    delegate = JYPYTask()
    task._active_delegate = delegate

    task.stop()

    assert task.is_stopped()
    assert delegate.is_stopped()


def test_xsrw_task_is_discoverable_by_dsl_loader() -> None:
    task_path = Path(__file__).parents[1] / "src" / "ymjh_bot" / "task" / "XSRW_task.py"

    task_class = load_task_class(task_path)

    assert task_class is XSRWTask or task_class.task_key == "XSRW"
    assert task_class.task_name == "悬赏任务"

    available = {
        task_info["key"]: task_info["name"]
        for task_info in _load_available_tasks()
    }
    assert available["XSRW"] == "悬赏任务"
