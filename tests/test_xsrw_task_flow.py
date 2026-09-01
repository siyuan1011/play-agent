from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from botCore import ImageMatchResult, VisionEngine, load_task_class
from ymjh_bot.run_queue import _load_available_tasks
from ymjh_bot.task.JYPY_task import JYPYTask
from ymjh_bot.task.RCFB_task import RCFBTask
from ymjh_bot.task.XSRW_task import (
    BountyCardSnapshot,
    BountyPanelSnapshot,
    DailyBountyContext,
    DailyBountyPhase,
    XSRWTask,
)
from ymjh_bot.ym_game_task import YmGameTask


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
        XSRWTask.TEXT_DEPOSIT_NOTICE_PARTIAL,
        XSRWTask.TEXT_CATEGORY_JYPY,
        XSRWTask.TEXT_CATEGORY_JHJS,
        XSRWTask.TEXT_CHALLENGE_VICTORY,
        XSRWTask.TEXT_DAILY_PANEL_TITLE,
        XSRWTask.BTN_DAILY_CHALLENGE,
        XSRWTask.BTN_DAILY_CONFIRM,
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


@pytest.mark.parametrize(
    "fixture_name",
    ["daily_panel.webp", "daily_team_list.webp", "panel_accepted.webp", "jypy_victory.webp"],
)
def test_daily_bounty_confirm_rejects_non_confirmation_scenes(
    fixture_name: str,
) -> None:
    match = VisionEngine().match_binary_template(
        load_image(fixture_name),
        XSRWTask.BTN_DAILY_CONFIRM,
        mode="otsu_dark",
        threshold=XSRWTask.DAILY_CONFIRM_THRESHOLD,
        roi=XSRWTask.ROI_DAILY_CONFIRM,
    )

    assert not match.found


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


def test_partial_deposit_notice_matches_join_toast_occlusion() -> None:
    match = VisionEngine().match_binary_template(
        load_image("deposit_modal_join_toast.webp"),
        XSRWTask.DEPOSIT_NOTICE_TEMPLATES,
        mode="light_foreground",
        threshold=XSRWTask.DEPOSIT_NOTICE_THRESHOLD,
        roi=XSRWTask.ROI_DEPOSIT_NOTICE,
    )

    assert match.found
    assert match.score >= 0.99
    assert match.template_path == XSRWTask.TEXT_DEPOSIT_NOTICE_PARTIAL


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
        screenshot=load_image("deposit_modal_join_toast.webp"),
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


def test_deposit_resolver_does_not_click_unrelated_screen(monkeypatch) -> None:
    task = XSRWTask()
    task._vision = VisionEngine()
    clicks: list[tuple[int, int, int]] = []
    monkeypatch.setattr(
        task,
        "click_point",
        lambda x, y, *, offset: clicks.append((x, y, offset)),
    )

    assert not task.resolve_bounty_deposit_modal_if_visible(
        timeout_ms=0,
        initial_screenshot=load_image("activity.webp"),
    )
    assert clicks == []


def test_before_start_recovers_deposit_before_shared_startup(monkeypatch) -> None:
    task = XSRWTask()
    events: list[object] = []
    monkeypatch.setattr(
        task,
        "resolve_bounty_deposit_modal_if_visible",
        lambda **kwargs: events.append(("deposit", kwargs["timeout_ms"])) or True,
    )
    monkeypatch.setattr(YmGameTask, "before_start", lambda self: events.append("shared"))

    task.before_start()

    assert events == [("deposit", task.DEPOSIT_STARTUP_RECOVERY_MS), "shared"]


def test_open_bounty_panel_recovers_deposit_before_activity_navigation(monkeypatch) -> None:
    task = XSRWTask()
    snapshot = make_snapshot()
    events: list[str] = []
    monkeypatch.setattr(
        task,
        "resolve_bounty_deposit_modal_if_visible",
        lambda **kwargs: events.append("deposit") or True,
    )
    monkeypatch.setattr(
        task,
        "_wait_bounty_panel",
        lambda **kwargs: events.append("wait-panel") or snapshot,
    )
    monkeypatch.setattr(
        task,
        "open_activity_panel",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("不应打开活动面板")),
    )

    assert task.open_bounty_panel(refresh=False) is snapshot
    assert events == ["deposit", "wait-panel"]


def test_refresh_recovers_deposit_before_reopening_activity(monkeypatch) -> None:
    task = XSRWTask()
    snapshot = make_snapshot()
    refresh_match = ImageMatchResult(True, 0.99, (1000, 140), (980, 120, 1020, 160))
    events: list[str] = []
    monkeypatch.setattr(
        task,
        "resolve_bounty_deposit_modal_if_visible",
        lambda **kwargs: events.append("deposit") or True,
    )
    monkeypatch.setattr(task, "_binary_match", lambda *args, **kwargs: refresh_match)
    monkeypatch.setattr(task, "tap", lambda *args: events.append("refresh"))
    monkeypatch.setattr(task, "wait", lambda wait_ms: None)
    monkeypatch.setattr(
        task,
        "_wait_bounty_panel",
        lambda **kwargs: events.append("wait-panel") or snapshot,
    )
    monkeypatch.setattr(
        task,
        "open_bounty_panel",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("不应重新打开活动面板")),
    )

    assert task.refresh_bounty_panel() is snapshot
    assert events == ["deposit", "wait-panel", "refresh", "wait-panel"]


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
        lambda card: categories.append(card.category),
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
    monkeypatch.setattr(task, "_wait_for_daily_bounty_panel_to_close", lambda: True)
    monkeypatch.setattr(task, "_log", lambda *args: None)

    task.enter_daily_bounty_challenge()

    assert taps == [(1165, 660), (1067, 597)]
    assert waits == [task.DAILY_ENTRY_SETTLE_MS]


def test_daily_bounty_entry_retries_when_panel_does_not_close(monkeypatch) -> None:
    task = XSRWTask()
    matches = iter(
        (
            ImageMatchResult(True, 0.99, (1067, 597), (975, 560, 1160, 635)),
            ImageMatchResult(True, 0.99, (1067, 597), (975, 560, 1160, 635)),
        )
    )
    taps: list[tuple[int, int]] = []
    screenshots: list[str] = []
    monkeypatch.setattr(task, "_wait_binary_match", lambda *args, **kwargs: next(matches))
    monkeypatch.setattr(task, "tap", lambda x, y: taps.append((x, y)))
    monkeypatch.setattr(task, "wait", lambda *args: None)
    monkeypatch.setattr(task, "_wait_for_daily_bounty_panel_to_close", lambda: False)
    monkeypatch.setattr(
        task,
        "save_debug_screenshot",
        lambda prefix: screenshots.append(prefix) or "entry-failed.png",
    )
    monkeypatch.setattr(task, "_log", lambda *args: None)

    with pytest.raises(RuntimeError, match="仍停留日常副本选择页"):
        task.enter_daily_bounty_challenge()

    assert taps == [(1067, 597), (1067, 597)]
    assert screenshots == ["xsrw_daily_entry_transition_failed"]


def test_daily_bounty_panel_close_verification_rejects_visible_panel(monkeypatch) -> None:
    task = XSRWTask()
    task._vision = VisionEngine()
    deadline_states = iter((False, True))
    monkeypatch.setattr(task, "_make_deadline", lambda timeout_ms: 1.0)
    monkeypatch.setattr(task, "_is_deadline_expired", lambda deadline: next(deadline_states))
    monkeypatch.setattr(task, "_remaining_ms", lambda deadline: 0)
    monkeypatch.setattr(task, "wake_from_power_saving_if_needed", lambda: False)
    monkeypatch.setattr(task, "screenshot", lambda: load_image("daily_panel.webp"))

    assert not task._wait_for_daily_bounty_panel_to_close()


def test_daily_bounty_creates_one_player_team_before_direct_challenge(monkeypatch) -> None:
    task = XSRWTask()
    events: list[object] = []

    monkeypatch.setattr(
        task,
        "close_all_panels",
        lambda **kwargs: events.append(("close", kwargs)),
    )
    monkeypatch.setattr(
        task,
        "create_team",
        lambda target, **kwargs: events.append(("create", target, kwargs)),
    )
    monkeypatch.setattr(
        task,
        "_restore_daily_panel_from_main_scene",
        lambda card: events.append(("restore", card.slot_index)),
    )
    monkeypatch.setattr(
        task,
        "enter_daily_bounty_challenge",
        lambda: events.append("enter"),
    )
    monkeypatch.setattr(task, "_log", lambda *args: None)

    context = DailyBountyContext(
        card=make_card(2, category="江湖纪事", action="前往"),
        delegate=RCFBTask(),
    )
    task.enter_daily_bounty_dungeon(context)

    assert context.phase is DailyBountyPhase.PANEL_RESTORED
    assert events == [
        (
            "close",
            {"timeout_ms": RCFBTask.DUNGEON_FAILURE_PANEL_CLEANUP_TIMEOUT_MS},
        ),
        ("create", "日常", {"min_member_count": 1}),
        (
            "close",
            {"timeout_ms": RCFBTask.DUNGEON_FAILURE_PANEL_CLEANUP_TIMEOUT_MS},
        ),
        ("restore", 2),
        "enter",
    ]


def test_restore_daily_panel_clicks_only_original_card(monkeypatch) -> None:
    task = XSRWTask()
    original = make_card(2, category="江湖纪事", action="前往")
    restored = make_card(2, category="江湖纪事", action="前往")
    taps: list[tuple[int, int]] = []
    monkeypatch.setattr(
        task,
        "open_bounty_panel",
        lambda **kwargs: make_snapshot(
            make_card(0, category="江湖纪事", action="前往"),
            restored,
            make_card(3, category="江湖纪事", action="前往"),
        ),
    )
    monkeypatch.setattr(task, "tap", lambda x, y: taps.append((x, y)))
    monkeypatch.setattr(task, "wait", lambda *args: None)
    monkeypatch.setattr(task, "_log", lambda *args: None)

    task._restore_daily_panel_from_main_scene(original)

    assert taps == [restored.action_center]


def test_restore_daily_panel_fails_when_original_card_changes(monkeypatch) -> None:
    task = XSRWTask()
    original = make_card(2, category="江湖纪事", action="前往")
    screenshots: list[str] = []
    monkeypatch.setattr(
        task,
        "open_bounty_panel",
        lambda **kwargs: make_snapshot(
            make_card(0, category="江湖纪事", action="前往"),
            make_card(2, category="聚义平冤", action="前往"),
        ),
    )
    monkeypatch.setattr(
        task,
        "save_debug_screenshot",
        lambda prefix: screenshots.append(prefix) or "changed.png",
    )

    with pytest.raises(RuntimeError, match="原第 3 卡位"):
        task._restore_daily_panel_from_main_scene(original)

    assert screenshots == ["xsrw_daily_original_card_changed"]


def test_daily_bounty_flow_reuses_shared_hangup_monitor(monkeypatch) -> None:
    task = XSRWTask()
    monitor_kwargs: list[dict] = []

    class FakeDailyDelegate:
        TASK_FLOW_TIMEOUT_MS = 1800000

        @staticmethod
        def is_stopped() -> bool:
            return False

        @staticmethod
        def monitor_dungeon_hangup_flow(**kwargs) -> None:
            monitor_kwargs.append(kwargs)

    monkeypatch.setattr(task, "is_stopped", lambda: False)

    task.run_daily_bounty_raid_flow(FakeDailyDelegate())  # type: ignore[arg-type]

    assert monitor_kwargs == [
        {
            "timeout_ms": 1800000,
            "context": "江湖纪事悬赏副本",
            "hangup_failure_screenshot_prefix": "xsrw_daily_hangup_state_failed",
            "timeout_screenshot_prefix": "xsrw_daily_raid_timeout",
        }
    ]


def test_daily_context_exists_before_first_forward_click(monkeypatch) -> None:
    task = XSRWTask()
    task._adb = object()  # type: ignore[assignment]
    task._vision = VisionEngine()
    delegate = RCFBTask()
    card = make_card(1, category="江湖纪事", action="前往")
    cleaned_contexts: list[DailyBountyContext] = []
    monkeypatch.setattr("ymjh_bot.task.XSRW_task.RCFBTask", lambda: delegate)
    monkeypatch.setattr(delegate, "setup", lambda *args, **kwargs: None)
    monkeypatch.setattr(delegate, "reset_startup_state", lambda: None)
    monkeypatch.setattr(
        task,
        "tap",
        lambda *args: (_ for _ in ()).throw(RuntimeError("forward failed")),
    )
    monkeypatch.setattr(
        task,
        "cleanup_daily_bounty_after_failure",
        cleaned_contexts.append,
    )

    with pytest.raises(RuntimeError, match="forward failed"):
        task._run_category_delegate(card)

    assert len(cleaned_contexts) == 1
    assert cleaned_contexts[0].card is card
    assert cleaned_contexts[0].phase is DailyBountyPhase.TARGET_OPENED
    assert task._daily_context is None


def test_daily_bounty_delegate_failure_cleans_dungeon_before_reraising(
    monkeypatch,
) -> None:
    task = XSRWTask()
    task._adb = object()  # type: ignore[assignment]
    task._vision = VisionEngine()
    delegate = RCFBTask()
    card = make_card(1, category="江湖纪事", action="前往")
    cleaned_phases: list[DailyBountyPhase] = []
    monkeypatch.setattr(task, "enter_daily_bounty_dungeon", lambda context: None)
    monkeypatch.setattr(task, "tap", lambda *args: None)
    monkeypatch.setattr(task, "wait", lambda *args: None)
    monkeypatch.setattr("ymjh_bot.task.XSRW_task.RCFBTask", lambda: delegate)
    monkeypatch.setattr(delegate, "setup", lambda *args, **kwargs: None)
    monkeypatch.setattr(delegate, "reset_startup_state", lambda: None)
    monkeypatch.setattr(
        task,
        "wait_for_daily_bounty_task",
        lambda current, **kwargs: None,
    )
    monkeypatch.setattr(
        task,
        "run_daily_bounty_raid_flow",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("raid failed")),
    )
    monkeypatch.setattr(
        task,
        "cleanup_daily_bounty_after_failure",
        lambda context: cleaned_phases.append(context.phase),
    )

    with pytest.raises(RuntimeError, match="raid failed"):
        task._run_category_delegate(card)

    assert cleaned_phases == [DailyBountyPhase.ENTRY_CONFIRMED]
    assert task._daily_context is None
    assert task._active_delegate is None


def test_daily_bounty_cleanup_failure_is_retained_for_queue_cleanup(monkeypatch) -> None:
    task = XSRWTask()
    task._adb = object()  # type: ignore[assignment]
    task._vision = VisionEngine()
    delegate = RCFBTask()
    card = make_card(1, category="江湖纪事", action="前往")
    cleanup_calls: list[DailyBountyPhase] = []
    monkeypatch.setattr(task, "enter_daily_bounty_dungeon", lambda context: None)
    monkeypatch.setattr(task, "tap", lambda *args: None)
    monkeypatch.setattr(task, "wait", lambda *args: None)
    monkeypatch.setattr("ymjh_bot.task.XSRW_task.RCFBTask", lambda: delegate)
    monkeypatch.setattr(delegate, "setup", lambda *args, **kwargs: None)
    monkeypatch.setattr(delegate, "reset_startup_state", lambda: None)
    monkeypatch.setattr(
        task,
        "wait_for_daily_bounty_task",
        lambda current, **kwargs: None,
    )
    monkeypatch.setattr(
        task,
        "run_daily_bounty_raid_flow",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("raid failed")),
    )

    def cleanup(context: DailyBountyContext) -> None:
        cleanup_calls.append(context.phase)
        if len(cleanup_calls) == 1:
            raise RuntimeError("exit failed")

    monkeypatch.setattr(task, "cleanup_daily_bounty_after_failure", cleanup)

    with pytest.raises(RuntimeError, match="阶段 entry_confirmed 清理异常：exit failed"):
        task._run_category_delegate(card)

    assert task._daily_context is not None
    assert task._daily_context.delegate is delegate

    task.cleanup_after_failure("queue retry")

    assert cleanup_calls == [
        DailyBountyPhase.ENTRY_CONFIRMED,
        DailyBountyPhase.ENTRY_CONFIRMED,
    ]
    assert task._daily_context is None


def test_pre_entry_cleanup_dismisses_known_panel_before_normalizing(monkeypatch) -> None:
    task = XSRWTask()
    delegate = RCFBTask()
    context = DailyBountyContext(
        card=make_card(0, category="江湖纪事", action="前往"),
        delegate=delegate,
        phase=DailyBountyPhase.TEAM_CREATED,
    )
    events: list[object] = []
    monkeypatch.setattr(delegate, "wake_from_power_saving_if_needed", lambda: False)
    monkeypatch.setattr(
        delegate,
        "close_all_panels",
        lambda **kwargs: events.append(("close", kwargs)),
    )
    monkeypatch.setattr(delegate, "detect_and_mark_dungeon_scene", lambda: False)
    monkeypatch.setattr(
        delegate,
        "normalize_outside_dungeon_after_failure",
        lambda **kwargs: events.append(("normalize", kwargs)),
    )
    monkeypatch.setattr(
        task,
        "_dismiss_known_daily_bounty_panels",
        lambda: events.append("dismiss"),
    )
    monkeypatch.setattr(task, "_log", lambda *args: None)

    task.cleanup_daily_bounty_after_failure(context)

    assert events == [
        "dismiss",
        (
            "close",
            {"timeout_ms": delegate.DUNGEON_FAILURE_PANEL_CLEANUP_TIMEOUT_MS},
        ),
        ("normalize", {"panels_already_closed": True}),
    ]


def test_known_bounty_panel_cleanup_clicks_outside_without_forward(monkeypatch) -> None:
    task = XSRWTask()
    visible = make_snapshot(
        make_card(0, category="江湖纪事", action="前往"),
        make_card(1, category="江湖纪事", action="前往"),
    )
    hidden = BountyPanelSnapshot(
        screenshot=visible.screenshot,
        visible=False,
        daily_complete=False,
        cards=(),
    )
    panel_states = iter((visible, hidden))
    clicks: list[tuple[int, int]] = []
    monkeypatch.setattr(task, "screenshot", lambda: visible.screenshot)
    monkeypatch.setattr(task, "read_bounty_panel", lambda screenshot: next(panel_states))
    monkeypatch.setattr(
        task,
        "_binary_match",
        lambda *args, **kwargs: ImageMatchResult(False, 0.0, None, None),
    )
    monkeypatch.setattr(
        task,
        "click_point",
        lambda x, y, *, offset: clicks.append((x, y)),
    )
    monkeypatch.setattr(task, "wait", lambda *args: None)
    monkeypatch.setattr(task, "_log", lambda *args: None)

    task._dismiss_known_daily_bounty_panels()

    assert clicks == [task.DAILY_BOUNTY_PANEL_DISMISS_POINT]


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
