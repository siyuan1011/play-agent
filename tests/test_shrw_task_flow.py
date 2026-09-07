from __future__ import annotations

import numpy as np
import pytest

from botCore import VisionEngine
from botCore.vision import load_image
from ymjh_bot.task.SHRW_task import SHRWTask


@pytest.mark.parametrize(
    ("settings", "expected_map"),
    [
        ({"task_type": "mining", "material": "stone"}, "zhongyuan"),
        ({"task_type": "herb", "material": "wild_ginseng"}, "jiangnan"),
        ({"task_type": "herb", "material": "lingzhi"}, "saibei"),
        ({"task_type": "herb", "material": "wildflower"}, "zhongyuan"),
        ({"task_type": "logging", "material": "pine"}, "jiangnan"),
        ({"task_type": "wool", "material": "cashmere"}, "buwenchun"),
    ],
)
def test_material_settings_select_the_required_target_map(settings, expected_map) -> None:
    assert SHRWTask(settings).material.map_key == expected_map


@pytest.mark.parametrize(
    ("material", "expected_filter_index"),
    [
        ("wool", 0),
        ("cashmere", 0),
        ("reindeer_hair", 1),
        ("reindeer_down", 1),
    ],
)
def test_wool_outputs_use_the_two_available_animal_map_filters(
    material, expected_filter_index
) -> None:
    task = SHRWTask({"task_type": "wool", "material": material})

    assert task.material.item_index == expected_filter_index


@pytest.mark.parametrize(
    ("material", "expected_slot"),
    [
        ("wool", 0),
        ("reindeer_hair", 0),
        ("cashmere", 1),
        ("reindeer_down", 1),
    ],
)
def test_wool_outputs_select_the_corresponding_gather_action_row(
    material, expected_slot
) -> None:
    task = SHRWTask({"task_type": "wool", "material": material})

    assert task.material.gather_slot == expected_slot


def test_material_click_uses_the_expected_expanded_row_icon() -> None:
    task = SHRWTask({"task_type": "mining", "material": "stone"})
    clicks: list[tuple[int, int, int]] = []
    expected_y = 580 + 87
    task.rewind_life_panel = lambda: None  # type: ignore[method-assign]
    task.screenshot = lambda: np.zeros((720, 1280, 3), dtype=np.uint8)  # type: ignore[method-assign]
    task.find_life_material_icon_centers = lambda _image: [(207, expected_y)]  # type: ignore[method-assign]
    task.click_point = lambda x, y, *, offset: clicks.append((x, y, offset))  # type: ignore[method-assign]
    task.wait = lambda _milliseconds: None  # type: ignore[method-assign]

    task.click_configured_material(header_y=580)

    assert clicks == [(207, expected_y, 0)]


def test_material_click_uses_the_visible_row_index_before_the_last_row() -> None:
    task = SHRWTask({"task_type": "logging", "material": "pine"})
    clicks: list[tuple[int, int, int]] = []
    centers = [(207, y) for y in (331, 411, 493, 573, 655)]
    task.rewind_life_panel = lambda: None  # type: ignore[method-assign]
    task.scroll_life_panel_up = lambda _distance: None  # type: ignore[method-assign]
    task.screenshot = lambda: np.zeros((720, 1280, 3), dtype=np.uint8)  # type: ignore[method-assign]
    task.find_life_material_icon_centers = lambda _image: centers  # type: ignore[method-assign]
    task.click_point = lambda x, y, *, offset: clicks.append((x, y, offset))  # type: ignore[method-assign]
    task.wait = lambda _milliseconds: None  # type: ignore[method-assign]

    task.click_configured_material(header_y=490)

    assert clicks == [(207, 655, 0)]


def test_choose_resource_marker_prefers_the_configured_map_anchor() -> None:
    task = SHRWTask({"task_type": "mining", "material": "stone"})
    task.screenshot = lambda: np.zeros((720, 1280, 3), dtype=np.uint8)  # type: ignore[method-assign]
    task.is_map_visible = lambda _image: True  # type: ignore[method-assign]
    task.find_resource_map_marker_centers = lambda _image: [  # type: ignore[method-assign]
        (900, 120),
        (615, 527),
        (671, 519),
    ]
    task._log = lambda _message: None  # type: ignore[method-assign]

    assert task.choose_resource_marker(set()) == (615, 527)


def test_choose_resource_marker_requires_a_newly_filtered_map_icon() -> None:
    task = SHRWTask({"task_type": "mining", "material": "stone"})
    baseline = np.zeros((720, 1280, 3), dtype=np.uint8)
    filtered = baseline.copy()
    filtered[490:565, 580:655] = 255
    task._map_filter_baseline = baseline
    task.screenshot = lambda: filtered  # type: ignore[method-assign]
    task.is_map_visible = lambda _image: True  # type: ignore[method-assign]
    task.find_resource_map_marker_centers = lambda _image: [  # type: ignore[method-assign]
        (900, 120),
        (615, 527),
    ]
    task._log = lambda _message: None  # type: ignore[method-assign]

    assert task.choose_resource_marker(set()) == (615, 527)


def test_gather_button_requires_the_green_diamond_and_light_label() -> None:
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    image[30:44, 80:310] = (0, 0, 255)
    image[440:490, 990:1040] = (255, 255, 255)
    image[435:500, 900:955] = (40, 220, 40)

    assert SHRWTask.find_scene_gather_actions(image) == [SHRWTask.POINT_GATHER_ACTION]


def test_gather_button_is_not_detected_inside_a_non_scene_panel() -> None:
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    image[440:490, 990:1040] = (255, 255, 255)
    image[435:500, 900:955] = (255, 255, 255)

    assert SHRWTask.find_scene_gather_actions(image) == []


def test_loading_scene_is_not_treated_as_a_non_scene_panel() -> None:
    loading = np.zeros((720, 1280, 3), dtype=np.uint8)
    # 模拟跨图加载进度条的已加载与未加载两段；中部会被动效遮挡。
    loading[600:614, 260:390] = (170, 170, 170)
    loading[600:614, 820:1025] = (170, 170, 170)

    assert SHRWTask.is_scene_transition_loading(loading)


def test_wait_for_loading_recovery_requires_main_scene() -> None:
    task = SHRWTask({"task_type": "mining", "material": "stone"})
    loading = np.zeros((720, 1280, 3), dtype=np.uint8)
    main_scene = np.zeros((720, 1280, 3), dtype=np.uint8)
    main_scene[30:44, 80:310] = (0, 0, 255)
    screenshots = iter([loading, main_scene])
    task.screenshot = lambda: next(screenshots)  # type: ignore[method-assign]
    task.wait = lambda _milliseconds: None  # type: ignore[method-assign]

    assert task.wait_for_main_scene_after_loading()


def test_life_panel_detector_does_not_confuse_light_map_background() -> None:
    map_background = np.full((720, 1280, 3), 245, dtype=np.uint8)
    panel = map_background.copy()
    panel[4:70, 4:128] = 45

    assert not SHRWTask.is_life_filter_panel_visible(map_background)
    assert SHRWTask.is_life_filter_panel_visible(panel)


def test_initial_map_filter_sequence_clears_before_opening_life_sidebar() -> None:
    task = SHRWTask({"task_type": "mining", "material": "stone"})
    events: list[str] = []
    task.wake_from_power_saving_if_needed = lambda: events.append("wake")  # type: ignore[method-assign]
    task.close_all_panels = lambda **_kwargs: events.append("close_panels")  # type: ignore[method-assign]
    task.open_map = lambda: events.append("open_map")  # type: ignore[method-assign]
    task.select_target_map = lambda: events.append("select_map")  # type: ignore[method-assign]
    task.collapse_life_filter_panel_if_visible = (  # type: ignore[method-assign]
        lambda: events.append("collapse_stale_sidebar")
    )
    task.clear_existing_map_filters = (  # type: ignore[method-assign]
        lambda: events.append("clear_filters")
    )
    task.open_life_filter_panel = (  # type: ignore[method-assign]
        lambda: events.append("open_life_sidebar")
    )
    task.collapse_expanded_life_skill_if_needed = lambda: None  # type: ignore[method-assign]
    task.open_configured_life_skill = lambda: 580  # type: ignore[method-assign]
    task.click_configured_material = (  # type: ignore[method-assign]
        lambda _header_y: events.append("select_material")
    )
    task.collapse_life_filter_panel = (  # type: ignore[method-assign]
        lambda: events.append("collapse_sidebar")
    )
    task.wait = lambda _milliseconds: None  # type: ignore[method-assign]
    task._log = lambda _message: None  # type: ignore[method-assign]

    task.select_configured_resource_on_map()

    assert events == [
        "wake",
        "close_panels",
        "open_map",
        "select_map",
        "collapse_stale_sidebar",
        "clear_filters",
        "open_life_sidebar",
        "select_material",
        "collapse_sidebar",
    ]


def test_collection_waits_for_auto_path_start_and_end_before_gathering() -> None:
    task = SHRWTask(
        {"task_type": "mining", "material": "stone", "loop_lines": False}
    )
    events: list[str] = []
    task.select_configured_resource_on_map = lambda: events.append("select")  # type: ignore[method-assign]
    task.choose_resource_marker = lambda _visited: (615, 527)  # type: ignore[method-assign]
    task.click_point = lambda *_args, **_kwargs: events.append("marker")  # type: ignore[method-assign]
    task.wait = lambda _milliseconds: None  # type: ignore[method-assign]
    task.close_map_after_marker_click = lambda: events.append("close_map")  # type: ignore[method-assign]
    task.wait_resource_auto_path_started = (  # type: ignore[method-assign]
        lambda **_kwargs: events.append("auto_path_started") or True
    )
    task.wait_auto_pathfinding = (  # type: ignore[method-assign]
        lambda **_kwargs: events.append("auto_path_finished") or True
    )
    task.wake_from_power_saving_if_needed = lambda: events.append("wake")  # type: ignore[method-assign]
    task.gather_arrived_resource = (  # type: ignore[method-assign]
        lambda: events.append("gather") or True
    )
    task._log = lambda _message: None  # type: ignore[method-assign]

    task.collect_life_material()

    assert events.index("auto_path_started") < events.index("auto_path_finished")
    assert events.index("auto_path_finished") < events.index("gather")


def test_continuous_collection_reuses_preserved_filter_without_reselecting() -> None:
    task = SHRWTask(
        {"task_type": "mining", "material": "stone", "loop_lines": True}
    )
    selections: list[str] = []
    marker_visits: list[set[tuple[int, int]]] = []
    reopened: list[str] = []
    gather_count = 0
    task.select_configured_resource_on_map = lambda: selections.append("selected")  # type: ignore[method-assign]

    def choose_marker(visited: set[tuple[int, int]]) -> tuple[int, int]:
        marker_visits.append(set(visited))
        return 615, 527

    def gather() -> bool:
        nonlocal gather_count
        gather_count += 1
        if gather_count == 2:
            task.loop_lines = False
        return True

    task.choose_resource_marker = choose_marker  # type: ignore[method-assign]
    task.click_point = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
    task.wait = lambda _milliseconds: None  # type: ignore[method-assign]
    task.close_map_after_marker_click = lambda: None  # type: ignore[method-assign]
    task.wait_resource_auto_path_started = lambda **_kwargs: True  # type: ignore[method-assign]
    task.wait_auto_pathfinding = lambda **_kwargs: True  # type: ignore[method-assign]
    task.wake_from_power_saving_if_needed = lambda: None  # type: ignore[method-assign]
    task.gather_arrived_resource = gather  # type: ignore[method-assign]
    task.open_existing_resource_map = lambda: reopened.append("map")  # type: ignore[method-assign]
    task._log = lambda _message: None  # type: ignore[method-assign]

    task.collect_life_material()

    assert selections == ["selected"]
    assert marker_visits == [set(), set()]
    assert reopened == ["map"]


def test_missing_gather_action_skips_marker_and_tries_the_next_one() -> None:
    task = SHRWTask(
        {"task_type": "mining", "material": "stone", "loop_lines": False}
    )
    reopened: list[str] = []
    markers = iter([(615, 527), (671, 519)])
    gathers = iter([False, True])
    task.select_configured_resource_on_map = lambda: None  # type: ignore[method-assign]
    task.choose_resource_marker = lambda _visited: next(markers)  # type: ignore[method-assign]
    task.click_point = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
    task.wait = lambda _milliseconds: None  # type: ignore[method-assign]
    task.close_map_after_marker_click = lambda: None  # type: ignore[method-assign]
    task.wait_resource_auto_path_started = lambda **_kwargs: True  # type: ignore[method-assign]
    task.wait_auto_pathfinding = lambda **_kwargs: True  # type: ignore[method-assign]
    task.wake_from_power_saving_if_needed = lambda: None  # type: ignore[method-assign]
    task.gather_arrived_resource = lambda: next(gathers)  # type: ignore[method-assign]
    task.open_existing_resource_map = lambda: reopened.append("map")  # type: ignore[method-assign]
    task._log = lambda _message: None  # type: ignore[method-assign]

    task.collect_life_material()

    assert reopened == ["map"]


@pytest.mark.parametrize("task_type", ["mining", "logging"])
def test_all_known_tool_level_templates_exist_and_are_recognized(task_type) -> None:
    material = "stone" if task_type == "mining" else "deadwood"
    task = SHRWTask({"task_type": task_type, "material": material})
    task._vision = VisionEngine()
    templates = task.configured_gather_templates()

    assert len(templates) == 6
    for template_path in templates:
        template = load_image(template_path)
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        image[30:44, 80:310] = (0, 0, 255)
        height, width = template.shape[:2]
        image[438 : 438 + height, 907 : 907 + width] = template
        image[440:460, 990:1010] = (255, 255, 255)

        assert task.find_configured_gather_action(image) == task.POINT_GATHER_ACTIONS[0]


def test_cashmere_uses_second_action_row_template() -> None:
    task = SHRWTask({"task_type": "wool", "material": "cashmere"})
    task._vision = VisionEngine()
    template = load_image(task.configured_gather_templates()[0])
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    image[30:44, 80:310] = (0, 0, 255)
    height, width = template.shape[:2]
    image[525 : 525 + height, 883 : 883 + width] = template
    image[535:555, 975:995] = (255, 255, 255)

    assert task.find_configured_gather_action(image) == task.POINT_GATHER_ACTIONS[1]


def test_gather_clicks_once_then_waits_until_action_disappears() -> None:
    task = SHRWTask({"task_type": "logging", "material": "eucalyptus"})
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    clicks: list[tuple[int, int]] = []
    task.screenshot = lambda: image  # type: ignore[method-assign]
    task.find_configured_gather_action = (  # type: ignore[method-assign]
        lambda _image: task.POINT_GATHER_ACTIONS[0]
    )
    task.is_main_scene = lambda _image: True  # type: ignore[method-assign]
    task.wait_gather_action_complete = lambda: "completed"  # type: ignore[method-assign]
    task.click_point = (  # type: ignore[method-assign]
        lambda x, y, **_kwargs: clicks.append((x, y))
    )
    task.wait = lambda _milliseconds: None  # type: ignore[method-assign]
    task._log = lambda _message: None  # type: ignore[method-assign]

    assert task.gather_arrived_resource()
    assert clicks == [task.POINT_GATHER_ACTIONS[0]]
