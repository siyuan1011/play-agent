"""Headless runner for the YMJH task queue saved by the UI."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    src_dir = Path(__file__).resolve().parents[1]
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

from botCore import ADBClient, GameTask, RunLogger, VisionEngine, load_task_class
from ymjh_bot.runner.task_queue_runner import TaskQueueRunner
from ymjh_bot.ui.task_queue_state import (
    HSLJ_TASK_KEY,
    SHRW_TASK_KEY,
    clear_progress,
    load_state_for_serial,
    normalize_hslj_settings,
    normalize_shrw_settings,
    restore_selected_tasks,
    safe_serial_name,
    save_state,
    serial_run_lock,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _task_dir() -> Path:
    return Path(__file__).resolve().parent / "task"


def _state_dir() -> Path:
    return Path(__file__).resolve().parent / ".task_queue_states"


def _visible_task_class(task_class: type[GameTask]) -> bool:
    return bool(getattr(task_class, "task_visible", True)) and not bool(
        task_class.__dict__.get("__abstract_task__", False)
    )


def _load_available_tasks() -> list[dict[str, Any]]:
    available: list[dict[str, Any]] = []
    for file_path in sorted(_task_dir().glob("*_task.py")):
        if file_path.name.startswith("_"):
            continue
        task_class = load_task_class(file_path)
        if not _visible_task_class(task_class):
            continue
        available.append(
            {
                "key": getattr(task_class, "task_key", task_class.__name__),
                "name": getattr(task_class, "task_name", task_class.__name__),
                "class": task_class,
                "file": str(file_path),
            }
        )
    return available


def _task_instances(selected_tasks: list[dict[str, Any]], settings: dict[str, Any]) -> list[GameTask]:
    instances: list[GameTask] = []
    for task_info in selected_tasks:
        task_class = task_info["class"]
        if str(task_info.get("key") or "") == HSLJ_TASK_KEY:
            instances.append(
                task_class(
                    hslj_settings=normalize_hslj_settings(settings.get(HSLJ_TASK_KEY)),
                )
            )
        elif str(task_info.get("key") or "") == SHRW_TASK_KEY:
            instances.append(
                task_class(
                    shrw_settings=normalize_shrw_settings(settings.get(SHRW_TASK_KEY)),
                )
            )
        else:
            instances.append(task_class())
    return instances


def _timestamp() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _print(message: str) -> None:
    print(f"[{_timestamp()}] {message}", flush=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True, help="ADB serial, for example 127.0.0.1:16416")
    parser.add_argument("--adb-path", default="adb", help="ADB executable path")
    parser.add_argument(
        "--clear-progress",
        action="store_true",
        help="Clear saved progress before starting while preserving queue order and settings.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable detailed template, coordinate, and polling logs.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    serial = str(args.serial).strip()
    if not serial:
        raise SystemExit("--serial cannot be empty")

    state_dir = _state_dir()
    legacy_state_path = Path(__file__).resolve().parent / ".task_queue_state.json"
    state, state_path = load_state_for_serial(
        state_dir,
        serial,
        legacy_path=legacy_state_path,
        fallback_adb_path=args.adb_path,
    )
    state["serial"] = serial
    if args.clear_progress:
        state = clear_progress(state)
        save_state(state_path, state)

    available_tasks = _load_available_tasks()
    selected_tasks, missing = restore_selected_tasks(
        available_tasks,
        state.get("selected_task_keys", []),
    )
    for key in missing:
        _print(f"[WARN] saved task not found, skipped: {key}")
    if not selected_tasks:
        _print("[ERROR] no selected tasks in saved queue state")
        return 2

    task_names = [str(task.get("name") or task.get("key")) for task in selected_tasks]
    _print(f"STATE_PATH={state_path}")
    _print(f"TASK_QUEUE={' -> '.join(task_names)}")

    run_lock = serial_run_lock(state_dir, serial)
    if not run_lock.acquire():
        _print(f"[ERROR] {serial} already has a running queue lock")
        return 3

    try:
        logger = RunLogger(base_dir=_repo_root() / "logs" / safe_serial_name(serial))
        _print(f"RUN_DIR={logger.run_dir}")

        def save_progress(progress: dict[str, int]) -> None:
            state["progress"] = {
                "current_task_index": int(progress.get("current_task_index", 0)),
                "current_step_index": int(progress.get("current_step_index", 0)),
            }
            save_state(state_path, state)

        runner = TaskQueueRunner(
            _task_instances(selected_tasks, state.get("task_settings") or {}),
            ADBClient(adb_path=args.adb_path, serial=serial),
            VisionEngine(),
            logger=logger,
            event_callback=_print,
            progress_callback=save_progress,
            verbose=args.debug,
        )
        progress = state.get("progress")
        if isinstance(progress, dict):
            runner.load_progress(progress)
            _print(
                "RESTORED_PROGRESS="
                f"task:{progress.get('current_task_index', 0)},"
                f"step:{progress.get('current_step_index', 0)}"
            )
        runner.run()
    except Exception as exc:
        _print(f"[ERROR] {exc}")
        return 1
    finally:
        run_lock.release()

    state = clear_progress(state)
    save_state(state_path, state)
    _print("QUEUE_COMPLETED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
