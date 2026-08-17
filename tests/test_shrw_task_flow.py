from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from botCore import StepJumpException, StepStopException, VisionEngine, load_task_class
from ymjh_bot.run_queue import _load_available_tasks, _task_instances
from ymjh_bot.task.SHRW_task import LifeTaskUnavailable, LineEntry, SHRWTask
from ymjh_bot.ui.task_queue_state import (
    DEFAULT_SHRW_SETTINGS,
    SHRW_MATERIAL_OPTIONS,
    normalize_shrw_settings,
    normalize_task_key,
    normalize_task_settings,
)


SHRW_FIXTURES = Path(__file__).parent / "fixtures" / "ymjh" / "shrw"


def load_probe(name: str) -> np.ndarray:
    fixture_name = Path(name).with_suffix(".webp").name
    image = cv2.imread(str(SHRW_FIXTURES / fixture_name), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"missing SHRW fixture: {fixture_name}")
    return image


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, DEFAULT_SHRW_SETTINGS),
        (
            {
                "task_type": "挖矿",
                "material": "钨金矿",
                "loop_lines": "是",
                "line_scope": "互联分线",
            },
            {
                "task_type": "mining",
                "material": "tungsten_ore",
                "loop_lines": True,
                "line_scope": "interconnected",
            },
        ),
        (
            {
                "task_type": "伐木",
                "material": "碎石",
                "line_scope": "unknown",
            },
            {
                "task_type": "logging",
                "material": "deadwood",
                "loop_lines": False,
                "line_scope": "local",
            },
        ),
    ],
)
def test_normalize_shrw_settings(raw, expected) -> None:
    assert normalize_shrw_settings(raw) == expected


def test_normalize_task_settings_and_aliases() -> None:
    assert normalize_task_key("生活技能") == "SHRW"
    settings = normalize_task_settings(
        {
            "生活任务": {
                "task_type": "采草",
                "material": "灵芝",
                "line_scope": "本服",
            }
        }
    )
    assert settings["SHRW"] == {
        "task_type": "herb",
        "material": "lingzhi",
        "loop_lines": False,
        "line_scope": "local",
    }


def test_material_catalog_contains_every_requested_item() -> None:
    labels = {
        task_type: [label for _key, label in options]
        for task_type, options in SHRW_MATERIAL_OPTIONS.items()
    }
    assert labels == {
        "mining": ["碎石", "黄铜矿", "立银矿", "金矿", "祖母绿矿", "钨晶矿"],
        "herb": ["杂草", "野花", "朱果", "地灵果", "野山参", "灵芝"],
        "logging": ["枯木", "翠竹", "榆树", "枫树", "松树", "桉树"],
        "wool": ["羊毛", "驯鹿毛", "羊绒", "驯鹿绒"],
    }


def test_shrw_task_is_discoverable_and_headless_settings_are_injected() -> None:
    task_path = Path(__file__).parents[1] / "src" / "ymjh_bot" / "task" / "SHRW_task.py"
    task_class = load_task_class(task_path)
    assert task_class.task_key == "SHRW"
    assert task_class.task_name == "生活任务"

    available = {task["key"]: task for task in _load_available_tasks()}
    instance = _task_instances(
        [available["SHRW"]],
        {
            "SHRW": {
                "task_type": "采毛",
                "material": "羊绒",
                "loop_lines": True,
                "line_scope": "互联",
            }
        },
    )[0]
    assert instance.task_type == "wool"
    assert instance.material_key == "cashmere"
    assert instance.loop_lines
    assert instance.line_scope == "interconnected"


def test_visual_states_match_real_device_probes() -> None:
    life_panel = load_probe("life_panel.png")
    world_map = load_probe("stone_world_map.png")
    local_map = load_probe("stone_region_map.png")
    interconnected_panel = load_probe("line_panel.png")
    local_panel = load_probe("local_scope_page.png")
    diamond_arrived = load_probe("after_smoke_fail_2.png")
    gathering = load_probe("gather_label_click_1s.png")
    gathered = load_probe("gather_label_click_12s.png")

    assert SHRWTask.is_life_panel_visible(life_panel)
    assert SHRWTask.is_filtered_map_visible(world_map)
    assert SHRWTask.is_filtered_map_visible(local_map)
    assert SHRWTask.find_world_resource_regions(world_map)
    assert SHRWTask.find_local_resource_nodes(local_map)
    assert SHRWTask.detect_line_panel_scope(interconnected_panel) == "interconnected"
    assert SHRWTask.detect_line_panel_scope(local_panel) == "local"
    assert len(SHRWTask.find_line_entry_centers(interconnected_panel)) == 3
    assert len(SHRWTask.find_line_entry_centers(local_panel)) == 1
    arrived_actions = SHRWTask.find_scene_gather_actions(diamond_arrived)
    assert len(arrived_actions) == 1
    assert 995 <= arrived_actions[0][0] <= 1010
    assert 450 <= arrived_actions[0][1] <= 475
    gathering_actions = SHRWTask.find_scene_gather_actions(gathering)
    assert len(gathering_actions) == 1
    assert 990 <= gathering_actions[0][0] <= 1010
    assert 450 <= gathering_actions[0][1] <= 475
    assert SHRWTask.is_gathering_in_progress(gathering)
    assert not SHRWTask.is_gathering_in_progress(diamond_arrived)
    assert not SHRWTask.find_scene_gather_actions(gathered)
    assert not SHRWTask.find_scene_gather_actions(world_map)


def test_non_loop_mode_runs_one_round() -> None:
    task = SHRWTask({"loop_lines": False})
    rounds: list[int] = []
    task.run_collection_round = lambda: rounds.append(1) or 2  # type: ignore[method-assign]
    task._log = lambda _message: None  # type: ignore[method-assign]

    task.collect_life_material()

    assert rounds == [1]


def test_loop_mode_waits_twenty_seconds_only_after_empty_round() -> None:
    task = SHRWTask({"loop_lines": True})
    outcomes = iter((2, 0))
    waits: list[int] = []

    def run_round() -> int:
        try:
            return next(outcomes)
        except StopIteration:
            raise StepStopException("test stop")

    task.run_collection_round = run_round  # type: ignore[method-assign]
    task.wait = waits.append  # type: ignore[method-assign]
    task._log = lambda _message: None  # type: ignore[method-assign]

    with pytest.raises(StepStopException):
        task.collect_life_material()

    assert waits == [20_000]


def test_round_visits_each_line_once_and_accumulates_gathers() -> None:
    task = SHRWTask({"line_scope": "互联"})
    entries = [
        LineEntry("interconnected", 1, (901, 74)),
        LineEntry("interconnected", 1, (901, 74)),
        LineEntry("interconnected", 2, (901, 152)),
    ]
    switched: list[int] = []
    task.enumerate_lines = lambda _scope: entries  # type: ignore[method-assign]
    task.switch_to_line = lambda entry: switched.append(entry.index)  # type: ignore[method-assign]
    task.collect_current_line = lambda: 3  # type: ignore[method-assign]

    assert task.run_collection_round() == 6
    assert switched == [1, 2]
    assert task._successful_gathers == 6


def test_known_unavailable_condition_jumps_to_successful_end() -> None:
    task = SHRWTask()
    task.enumerate_lines = lambda _scope: (_ for _ in ()).throw(  # type: ignore[method-assign]
        LifeTaskUnavailable("体力耗尽")
    )
    task._log = lambda _message: None  # type: ignore[method-assign]

    with pytest.raises(StepJumpException):
        task.run_collection_round()

    assert task._known_unavailable_reason == "体力耗尽"


def test_material_carousel_page_mapping() -> None:
    assert SHRWTask.MATERIAL_SPECS["stone"].page_index == 0
    assert SHRWTask.MATERIAL_SPECS["brass_ore"].slot_index == 1
    assert SHRWTask.MATERIAL_SPECS["silver_ore"].page_index == 1
    assert SHRWTask.MATERIAL_SPECS["tungsten_ore"].page_index == 4


def test_local_map_detection_uses_existing_world_button_template() -> None:
    task = SHRWTask()
    task._vision = VisionEngine()
    assert task.is_local_resource_map(load_probe("stone_region_map.png"))
    assert not task.is_local_resource_map(load_probe("stone_world_map.png"))


def test_close_map_also_closes_underlying_life_panel() -> None:
    task = SHRWTask()
    screenshots = iter(
        (
            load_probe("stone_region_map.png"),
            load_probe("life_panel.png"),
        )
    )
    clicks: list[tuple[int, int, int]] = []
    task.screenshot = lambda: next(screenshots)  # type: ignore[method-assign]
    task.click_point = (  # type: ignore[method-assign]
        lambda x, y, *, offset: clicks.append((x, y, offset))
    )
    task.wait = lambda _ms: None  # type: ignore[method-assign]

    task.close_map_if_visible()

    assert clicks == [(1235, 42, 0), (1235, 42, 0)]


def test_route_start_accepts_direct_short_path_arrival() -> None:
    task = SHRWTask()
    task.screenshot = lambda: load_probe("after_smoke_fail_2.png")  # type: ignore[method-assign]
    task._log = lambda _message: None  # type: ignore[method-assign]

    assert task.wait_resource_route_started(timeout_ms=100) == "arrived"


def test_gather_retries_once_when_first_click_only_dismounts() -> None:
    task = SHRWTask()
    actions = iter(
        (
            [(1004, 462)],
            [(1004, 462)],
            [(1004, 462)],
            [(1004, 462)],
            [],
            [],
        )
    )
    clicks: list[tuple[int, int, int]] = []
    task.screenshot = lambda: np.zeros((720, 1280, 3), dtype=np.uint8)  # type: ignore[method-assign]
    task.find_scene_gather_actions = lambda _image: next(actions)  # type: ignore[method-assign]
    task.click_point = (  # type: ignore[method-assign]
        lambda x, y, *, offset: clicks.append((x, y, offset))
    )
    task.wait = lambda _ms: None  # type: ignore[method-assign]
    task._log = lambda _message: None  # type: ignore[method-assign]

    assert task.gather_arrived_resource()
    assert clicks == [(1004, 462, 0), (1004, 462, 0)]
