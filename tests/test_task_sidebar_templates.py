from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from botCore import VisionEngine
from ymjh_bot.ym_game_task import YmGameTask


FIXTURES = Path(__file__).parent / "fixtures" / "ymjh"
SIDEBAR_FIXTURES = FIXTURES / "task_sidebar_v2"
VISION = VisionEngine()


def load_image(path: Path):
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    assert image is not None, path
    return image


def local_tab_slot_roi(panel: str) -> tuple[int, int, int, int]:
    center_x, center_y = YmGameTask.TASK_TAB_SLOT_CENTERS[panel]
    width, height = YmGameTask.TASK_TAB_TEMPLATE_SIZE
    margin = YmGameTask.TASK_TAB_SEARCH_MARGIN_PX
    return (
        center_x - width // 2 - margin,
        center_y - height // 2 - margin,
        width + margin * 2,
        height + margin * 2,
    )


def active_scores(image) -> dict[str, float]:
    return {
        panel: VISION.match_binary_template(
            image,
            template,
            mode="otsu_dark",
            threshold=0,
            roi=local_tab_slot_roi(panel),
        ).score
        for panel, template in YmGameTask.TASK_PANEL_ACTIVE_TEMPLATES.items()
    }


@pytest.mark.parametrize(
    ("fixture_name", "panel"),
    [
        ("day_task_tabs.webp", "任务"),
        ("night_task_tabs.webp", "任务"),
        ("current_task_tabs.webp", "任务"),
        ("bright_task_tabs.webp", "任务"),
        ("night_jianghu_tabs.webp", "江湖"),
        ("day_qiyu_tabs.webp", "奇遇"),
        ("old_jianghu_tabs.webp", "江湖"),
    ],
)
def test_binary_active_tabs_are_unique_across_old_new_and_map_backgrounds(
    fixture_name: str,
    panel: str,
) -> None:
    scores = active_scores(load_image(SIDEBAR_FIXTURES / fixture_name))

    assert scores[panel] >= 0.90
    assert [name for name, score in scores.items() if score >= 0.90] == [panel]
    assert max(score for name, score in scores.items() if name != panel) < 0.80


def test_binary_active_tabs_stay_below_point_eight_in_battle() -> None:
    scores = active_scores(load_image(SIDEBAR_FIXTURES / "battle_tabs.webp"))

    assert max(scores.values()) < 0.80


@pytest.mark.parametrize(
    ("fixture_name", "template", "expected_center"),
    [
        ("day_other_sidebar.webp", YmGameTask.TASK_SIDEBAR_ENTRY_V2, (22, 129)),
        ("day_collapsed_sidebar.webp", YmGameTask.TASK_SIDEBAR_EXPAND_V2, (22, 269)),
        ("night_collapsed_sidebar.webp", YmGameTask.TASK_SIDEBAR_EXPAND_V2, (22, 269)),
    ],
)
def test_light_foreground_entry_and_expand_are_precise(
    fixture_name: str,
    template: str,
    expected_center: tuple[int, int],
) -> None:
    match = VISION.match_binary_template(
        load_image(SIDEBAR_FIXTURES / fixture_name),
        template,
        mode="light_foreground",
        threshold=0.90,
    )

    assert match.found
    assert match.score >= 0.90
    assert match.center == expected_center


@pytest.mark.parametrize(
    ("fixture_name", "template"),
    [
        ("battle_sidebar.webp", YmGameTask.TASK_SIDEBAR_ENTRY_V2),
        ("battle_sidebar.webp", YmGameTask.TASK_SIDEBAR_EXPAND_V2),
        ("day_task_sidebar.webp", YmGameTask.TASK_SIDEBAR_ENTRY_V2),
        ("day_task_sidebar.webp", YmGameTask.TASK_SIDEBAR_EXPAND_V2),
        ("day_collapsed_sidebar.webp", YmGameTask.TASK_SIDEBAR_ENTRY_V2),
        ("day_other_sidebar.webp", YmGameTask.TASK_SIDEBAR_EXPAND_V2),
    ],
)
def test_entry_and_expand_foregrounds_stay_below_point_eight_on_negatives(
    fixture_name: str,
    template: str,
) -> None:
    match = VISION.match_binary_template(
        load_image(SIDEBAR_FIXTURES / fixture_name),
        template,
        mode="light_foreground",
        threshold=0,
    )

    assert match.score < 0.80


def test_old_and_new_fullscreen_task_panel_markers_score_at_least_point_nine() -> None:
    old_match = VISION.match_template(
        load_image(FIXTURES / "bprw_sidebar_failure_20260713_013453.webp"),
        YmGameTask.TEXT_TASK_PANEL_TITLE,
        threshold=0.9,
        roi=YmGameTask.ROI_TASK_PANEL_TITLE,
    )
    new_match = VISION.match_template(
        load_image(SIDEBAR_FIXTURES / "fullscreen_v2_left.webp"),
        YmGameTask.TASK_FULLSCREEN_PANEL_V2,
        threshold=0.9,
    )

    assert old_match.found and old_match.score >= 0.9
    assert new_match.found and new_match.score >= 0.9


def test_active_binary_match_routes_low_transparency_to_activation_path() -> None:
    template = load_image(Path(YmGameTask.ICON_TASK_RW))
    binary_mask = VISION._to_binary_foreground(template, "otsu_dark") > 0
    rng = np.random.default_rng(20260718)
    background = rng.integers(90, 230, size=template.shape, dtype=np.uint8)

    normal = background.copy()
    normal[binary_mask] = 0
    low_transparency = background.copy().astype(np.float32)
    low_transparency[binary_mask] *= 0.30
    low_transparency = np.uint8(np.clip(low_transparency, 0, 255))

    normal_match = VISION.match_binary_template(
        normal,
        YmGameTask.ICON_TASK_RW,
        mode="otsu_dark",
        threshold=0.90,
    )
    dormant_match = VISION.match_binary_template(
        low_transparency,
        YmGameTask.ICON_TASK_RW,
        mode="otsu_dark",
        threshold=0.90,
    )

    assert normal_match.found and normal_match.score >= 0.90
    assert not dormant_match.found
    assert dormant_match.score < 0.90


def test_sidebar_runtime_no_longer_declares_rgb_inactive_or_chat_v2_templates() -> None:
    obsolete_attributes = (
        "_".join(("TASK", "PANEL", "INACTIVE", "TEMPLATES")),
        "_".join(("TASK", "SIDEBAR", "OPEN", "TEMPLATES")),
        "_".join(("TASK", "SIDEBAR", "ENTRY", "TEMPLATES")),
        "_".join(("BTN", "CHAT", "SEND", "V2")),
        "_".join(("CHAT", "SEND", "TEMPLATES")),
    )

    assert all(not hasattr(YmGameTask, name) for name in obsolete_attributes)
    assert Path(YmGameTask.TASK_SIDEBAR_ENTRY_V2).is_file()
    assert Path(YmGameTask.TASK_SIDEBAR_EXPAND_V2).is_file()
    obsolete_chat_asset = Path(YmGameTask.TEMPLATES_DIR) / ("btn_chat_send" + "_v2.png")
    assert not obsolete_chat_asset.exists()
