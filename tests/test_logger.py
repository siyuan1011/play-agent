import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from botCore import GameTask, RunLogger


def test_run_logger_adds_timestamp_to_plain_event(tmp_path):
    logger = RunLogger(base_dir=tmp_path)

    logger.log_event({"message": "x"})

    event = json.loads(logger.events_path.read_text(encoding="utf-8").strip())
    assert event["message"] == "x"
    datetime.fromisoformat(event["ts"])


def test_run_logger_saves_named_screenshot_inside_current_run(tmp_path):
    logger = RunLogger(base_dir=tmp_path)

    path = logger.save_screenshot(
        np.zeros((10, 10, 3), dtype=np.uint8),
        prefix="activity failed",
    )

    output = Path(path)
    assert output.is_file()
    assert output.name.startswith("activity_failed_")


def test_run_logger_prunes_only_expired_managed_runs(tmp_path):
    now = datetime(2026, 7, 16, 12, 0, 0)
    old_run = tmp_path / "run_old"
    recent_run = tmp_path / "run_recent"
    unrelated = tmp_path / "keep.txt"
    for path in (old_run / "events.jsonl", recent_run / "events.jsonl", unrelated):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    old_timestamp = (now - timedelta(days=10)).timestamp()
    recent_timestamp = (now - timedelta(days=1)).timestamp()
    os.utime(old_run / "events.jsonl", (old_timestamp, old_timestamp))
    os.utime(recent_run / "events.jsonl", (recent_timestamp, recent_timestamp))

    logger = RunLogger(base_dir=tmp_path, retention_days=None)
    removed = logger.prune_expired_runs(retention_days=7, now=now)

    assert removed == [old_run]
    assert not old_run.exists()
    assert recent_run.exists()
    assert unrelated.exists()


def test_game_task_hides_debug_events_unless_verbose():
    task = GameTask()
    messages: list[str] = []
    task.setup(object(), object(), event_callback=messages.append)

    task._log("state changed")
    task._debug("raw match")

    assert messages == ["[GameTask] state changed"]

    task.setup(object(), object(), event_callback=messages.append, verbose=True)
    task._debug("raw match")

    assert messages[-1] == "[GameTask] raw match"
