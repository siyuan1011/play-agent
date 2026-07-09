from pathlib import Path

from ymjh_bot.ui.task_queue_state import (
    HSLJ_STRATEGY_FIXED_COUNT,
    HSLJ_STRATEGY_FIRST_WIN,
    HSLJ_STRATEGY_INFINITE,
    clear_progress,
    default_state,
    load_state_for_serial,
    normalize_hslj_settings,
    load_state,
    restore_selected_tasks,
    save_state,
    serial_run_lock,
    state_path_for_serial,
    safe_serial_name,
    task_keys_from_infos,
)


def hslj_settings(
    *,
    one_v_one_strategy=HSLJ_STRATEGY_FIRST_WIN,
    one_v_one_count=5,
    three_v_three_strategy=HSLJ_STRATEGY_FIXED_COUNT,
    three_v_three_count=5,
):
    return {
        "1v1": {"strategy": one_v_one_strategy, "count": one_v_one_count},
        "3v3": {"strategy": three_v_three_strategy, "count": three_v_three_count},
    }


def test_task_queue_state_read_write_defaults(tmp_path):
    path = tmp_path / "state.json"

    assert load_state(path) == default_state()

    state = default_state()
    state.update(
        {
            "adb_path": "custom-adb",
            "serial": "127.0.0.1:16416",
            "selected_task_keys": ["launch", "daily"],
            "progress": {"current_task_index": 1, "current_step_index": 2},
        }
    )

    save_state(path, state)

    loaded = load_state(path)
    assert loaded == {**state, "selected_task_keys": ["QDYX", "daily"]}


def test_restore_selected_tasks_keeps_saved_order_and_skips_missing():
    available = [
        {"key": "QDYX", "name": "Launch"},
        {"key": "daily", "name": "Daily"},
        {"key": "guild", "name": "Guild"},
    ]

    restored, missing = restore_selected_tasks(available, ["daily", "missing", "launch"])

    assert task_keys_from_infos(restored) == ["daily", "QDYX"]
    assert missing == ["missing"]


def test_clear_progress_preserves_queue_order():
    state = default_state()
    state["selected_task_keys"] = ["QDYX", "daily"]
    state["progress"] = {"current_task_index": 1, "current_step_index": 2}

    cleared = clear_progress(state)

    assert "progress" not in cleared
    assert cleared["selected_task_keys"] == ["QDYX", "daily"]


def test_serial_state_paths_are_filesystem_safe():
    state_dir = Path("states")

    assert state_path_for_serial(state_dir, "127.0.0.1:16416") == state_dir / "127.0.0.1_16416.json"
    assert safe_serial_name("") == "default"


def test_per_serial_task_settings_are_isolated(tmp_path):
    state_dir = tmp_path / "states"
    first_path = state_path_for_serial(state_dir, "127.0.0.1:16416")
    second_path = state_path_for_serial(state_dir, "127.0.0.1:16448")

    first_state = default_state()
    first_state["serial"] = "127.0.0.1:16416"
    first_state["task_settings"] = {"hslj": {"lunjian_count": 3, "infinite": False}}
    second_state = default_state()
    second_state["serial"] = "127.0.0.1:16448"
    second_state["task_settings"] = {"HSLJ": {"lunjian_count": 9, "infinite": True}}

    save_state(first_path, first_state)
    save_state(second_path, second_state)

    assert load_state(first_path)["task_settings"]["HSLJ"] == hslj_settings(three_v_three_count=3)
    assert load_state(second_path)["task_settings"]["HSLJ"] == hslj_settings(
        three_v_three_strategy=HSLJ_STRATEGY_INFINITE,
        three_v_three_count=9,
    )


def test_load_state_for_serial_migrates_legacy_state(tmp_path):
    state_dir = tmp_path / "states"
    legacy_path = tmp_path / ".task_queue_state.json"
    legacy_state = default_state()
    legacy_state.update(
        {
            "adb_path": "custom-adb",
            "serial": "127.0.0.1:16416",
            "selected_task_keys": ["hslj"],
            "task_settings": {"hslj": {"lunjian_count": 4, "infinite": False}},
        }
    )
    save_state(legacy_path, legacy_state)

    state, path = load_state_for_serial(state_dir, "", legacy_path=legacy_path)

    assert path == state_path_for_serial(state_dir, "127.0.0.1:16416")
    assert state["selected_task_keys"] == ["HSLJ"]
    assert state["task_settings"]["HSLJ"] == hslj_settings(three_v_three_count=4)


def test_old_task_keys_are_migrated_when_state_loads(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(
        """
{
  "selected_task_keys": ["launch", "bangpai", "hslj", "kyrw", "mksy", "pzsy", "zgwx", "hslj"],
  "task_settings": {
    "hslj": {"lunjian_count": 2, "infinite": false},
    "custom": {"enabled": true}
  }
}
""".strip(),
        encoding="utf-8",
    )

    state = load_state(path)

    assert state["selected_task_keys"] == ["QDYX", "BPRW", "HSLJ", "KYRW", "MKSY", "PZSY", "ZGWX"]
    assert state["task_settings"]["HSLJ"] == hslj_settings(three_v_three_count=2)
    assert state["task_settings"]["custom"] == {"enabled": True}


def test_hslj_settings_normalize_invalid_values():
    assert normalize_hslj_settings({"lunjian_count": "bad", "infinite": 1}) == hslj_settings(
        three_v_three_strategy=HSLJ_STRATEGY_INFINITE,
    )
    assert normalize_hslj_settings({"lunjian_count": 0})["3v3"]["count"] == 1


def test_hslj_settings_normalize_new_per_mode_schema():
    assert normalize_hslj_settings(
        {
            "1v1": {"strategy": HSLJ_STRATEGY_FIXED_COUNT, "count": "2"},
            "3v3": {"strategy": "bad", "count": 0},
        }
    ) == hslj_settings(
        one_v_one_strategy=HSLJ_STRATEGY_FIXED_COUNT,
        one_v_one_count=2,
        three_v_three_count=1,
    )


def test_serial_run_lock_blocks_same_serial_and_allows_release(tmp_path):
    state_dir = tmp_path / "states"
    first = serial_run_lock(state_dir, "127.0.0.1:16416")
    second = serial_run_lock(state_dir, "127.0.0.1:16416")
    other = serial_run_lock(state_dir, "127.0.0.1:16448")

    assert first.acquire()
    assert not second.acquire()
    assert other.acquire()

    first.release()
    other.release()
    assert second.acquire()
    second.release()
