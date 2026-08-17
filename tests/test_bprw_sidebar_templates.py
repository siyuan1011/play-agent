from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from botCore import VisionEngine
from ymjh_bot.task.BPRW_task import BPRWTask
from ymjh_bot.task.MKSY_task import MKSYTask
from ymjh_bot.task.PZSY_task import PZSYTask


FIXTURES = Path(__file__).parent / "fixtures" / "ymjh"
VISION = VisionEngine()


def load_image(path: Path | str) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    assert image is not None, path
    return image


@pytest.mark.parametrize(
    ("fixture_name", "template", "task_title"),
    [
        (
            "bprw_sidebar_feast_guests.webp",
            BPRWTask.TEXT_BANGPAI_FEAST_GUESTS,
            "大宴宾客",
        ),
        (
            "bprw_sidebar_construction_bangpai.webp",
            BPRWTask.TEXT_BANGPAI_CONSTRUCTION,
            "帮派建设",
        ),
        (
            "bprw_sidebar_scout_enemy.webp",
            BPRWTask.TEXT_BANGPAI_SCOUT_ENEMY,
            "刺探敌情",
        ),
        (
            "bprw_sidebar_emergency_rescue.webp",
            BPRWTask.TEXT_BANGPAI_EMERGENCY_RESCUE,
            "紧急救援",
        ),
        (
            "bprw_sidebar_jinling_escort.webp",
            BPRWTask.TEXT_BANGPAI_JINLING_ESCORT,
            "金陵护送",
        ),
        (
            "bprw_sidebar_buxiangweimou.webp",
            BPRWTask.TEXT_BANGPAI_BUXIANGWEIMOU,
            "不相为谋",
        ),
        (
            "bprw_sidebar_return.webp",
            BPRWTask.TEXT_BANGPAI_RETURN,
            "回帮复命",
        ),
    ],
)
def test_bprw_specific_sidebar_titles_match_real_task_states(
    fixture_name: str,
    template: str,
    task_title: str,
) -> None:
    match = VISION.match_template(
        load_image(FIXTURES / fixture_name),
        BPRWTask.SIDEBAR_BANGPAI_TASK_TEMPLATES,
        threshold=0.8,
    )

    assert match.found
    assert match.score >= 0.8
    assert match.template_path == template
    assert BPRWTask.SIDEBAR_BANGPAI_TASK_TITLE_BY_TEMPLATE[match.template_path] == task_title


@pytest.mark.parametrize(
    ("fixture_name", "template"),
    [
        ("bprw_sidebar_construction_daily.webp", BPRWTask.TEXT_BANGPAI_CONSTRUCTION),
        ("bangpai_debug_current_after_loop_timeout.webp", BPRWTask.TEXT_BANGPAI_RETURN),
    ],
)
def test_bprw_titles_remain_compatible_with_previous_visual_variants(
    fixture_name: str,
    template: str,
) -> None:
    roi = (
        (40, 135, 330, 430)
        if fixture_name == "bangpai_debug_current_after_loop_timeout.webp"
        else None
    )
    match = VISION.match_template(
        load_image(FIXTURES / fixture_name),
        template,
        threshold=0.8,
        roi=roi,
    )

    assert match.found
    assert match.score >= 0.8


def test_sidebar_title_wait_returns_exact_title_and_preserves_click_center(monkeypatch) -> None:
    task = BPRWTask()
    task._vision = VISION
    screenshot = np.zeros((720, 1280, 3), dtype=np.uint8)
    task_card = load_image(FIXTURES / "bprw_sidebar_return.webp")
    x, y = 40, 140
    screenshot[y : y + task_card.shape[0], x : x + task_card.shape[1]] = task_card

    monkeypatch.setattr(task, "screenshot", lambda: screenshot)
    monkeypatch.setattr(task, "wait", lambda *args, **kwargs: None)

    task_title = task.wait_bangpai_task_title_in_sidebar(
        timeout_ms=1500,
        threshold=0.8,
        interval_ms=500,
    )

    assert task_title == "回帮复命"
    assert task._last_match_center == (141, 162)


def test_bprw_sidebar_targets_do_not_include_generic_category_tags() -> None:
    generic_tags = {
        str(BPRWTask.TEMPLATES_DIR / "text_bangpai.png"),
        str(BPRWTask.TEMPLATES_DIR / "text_bangpai_daily.png"),
    }

    assert generic_tags.isdisjoint(BPRWTask.SIDEBAR_BANGPAI_TASK_TEMPLATES)


@pytest.mark.parametrize(
    "generic_tag",
    [
        BPRWTask.TEMPLATES_DIR / "text_bangpai.png",
        BPRWTask.TEMPLATES_DIR / "text_bangpai_daily.png",
    ],
)
def test_generic_bangpai_or_daily_prefix_alone_is_not_a_bprw_match(generic_tag: Path) -> None:
    screenshot = np.zeros((720, 1280, 3), dtype=np.uint8)
    tag = load_image(generic_tag)
    x, y = 55, 155
    screenshot[y : y + tag.shape[0], x : x + tag.shape[1]] = tag

    match = VISION.match_template(
        screenshot,
        BPRWTask.SIDEBAR_BANGPAI_TASK_TEMPLATES,
        threshold=0.8,
        roi=(40, 135, 330, 430),
    )

    assert not match.found


def test_real_banquet_sidebar_reproduces_old_false_positive_but_not_new_match() -> None:
    screenshot = load_image(FIXTURES / "banquet_sidebar_bangpai_prefix.webp")
    generic_templates = [
        str(BPRWTask.TEMPLATES_DIR / "text_bangpai.png"),
        str(BPRWTask.TEMPLATES_DIR / "text_bangpai_daily.png"),
    ]

    old_match = VISION.match_template(screenshot, generic_templates, threshold=0.7)
    new_match = VISION.match_template(
        screenshot,
        BPRWTask.SIDEBAR_BANGPAI_TASK_TEMPLATES,
        threshold=0.8,
    )

    assert old_match.found
    assert old_match.score >= 0.9
    assert not new_match.found
    assert new_match.score < 0.8


@pytest.mark.parametrize(
    "banquet_entry",
    [
        MKSYTask.BTN_MENKE_SHEYAN_ENTRY,
        PZSYTask.BTN_POZHEN_SHEYAN_ENTRY,
    ],
)
def test_banquet_activity_titles_do_not_match_bprw_titles(banquet_entry: str) -> None:
    match = VISION.match_template(
        load_image(banquet_entry),
        BPRWTask.SIDEBAR_BANGPAI_TASK_TEMPLATES,
        threshold=0.8,
    )

    assert not match.found
