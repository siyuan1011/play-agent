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
from ymjh_bot.runner.account_role_switcher import AccountRoleSwitcher
from ymjh_bot.runner.task_factory import create_task_instances
from ymjh_bot.runner.task_queue_runner import TaskQueueRunner
from ymjh_bot.ui.task_queue_state import (
    clear_progress,
    load_state_for_serial,
    normalize_selected_role_indices,
    role_indices_from_count,
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
    return create_task_instances(selected_tasks, settings)


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
    role_group = parser.add_mutually_exclusive_group()
    role_group.add_argument(
        "--role",
        action="append",
        type=int,
        choices=range(1, 6),
        help="Select one account role (1-5); repeat for an arbitrary combination.",
    )
    role_group.add_argument(
        "--roles",
        type=int,
        choices=range(1, 6),
        help="Compatibility option: select the first N account roles (1-5).",
    )
    return parser.parse_args(argv)


def resolve_role_indices(
    args: argparse.Namespace,
    state: dict[str, Any],
) -> tuple[list[int], bool]:
    """Resolve CLI or saved role selection and report whether CLI overrode it."""
    saved = normalize_selected_role_indices(state.get("selected_role_indices"))
    if args.role is not None:
        return sorted({role_number - 1 for role_number in args.role}), True
    if args.roles is not None:
        return role_indices_from_count(args.roles), True
    return saved, False


def apply_role_cli_selection(
    args: argparse.Namespace,
    state: dict[str, Any],
) -> tuple[dict[str, Any], list[int], bool]:
    """Apply a CLI role override and invalidate progress when its queue changes."""
    role_indices, overridden = resolve_role_indices(args, state)
    saved = normalize_selected_role_indices(state.get("selected_role_indices"))
    updated = state
    if overridden:
        updated = dict(state)
        updated["selected_role_indices"] = role_indices
    selection_changed = overridden and role_indices != saved
    if args.clear_progress or selection_changed:
        updated = clear_progress(updated)
    return updated, role_indices, bool(args.clear_progress or overridden)


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
    state, role_indices, should_save_role_state = apply_role_cli_selection(args, state)
    if should_save_role_state:
        save_state(state_path, state)

    if not role_indices:
        _print("[ERROR] no account role selected; select at least one role")
        return 2

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
    _print(f"ROLE_QUEUE={' -> '.join(str(index + 1) for index in role_indices)}")

    run_lock = serial_run_lock(state_dir, serial)
    if not run_lock.acquire():
        _print(f"[ERROR] {serial} already has a running queue lock")
        return 3

    try:
        logger = RunLogger(base_dir=_repo_root() / "logs" / safe_serial_name(serial))
        _print(f"RUN_DIR={logger.run_dir}")

        def save_progress(progress: dict[str, int]) -> None:
            state["progress"] = {
                "current_role_index": int(progress.get("current_role_index", 0)),
                "current_task_index": int(progress.get("current_task_index", 0)),
                "current_step_index": int(progress.get("current_step_index", 0)),
            }
            save_state(state_path, state)

        task_settings = state.get("task_settings") or {}

        def task_factory() -> list[GameTask]:
            return _task_instances(selected_tasks, task_settings)

        runner = TaskQueueRunner(
            task_factory(),
            ADBClient(adb_path=args.adb_path, serial=serial),
            VisionEngine(),
            logger=logger,
            event_callback=_print,
            progress_callback=save_progress,
            verbose=args.debug,
            role_indices=role_indices,
            task_factory=task_factory if len(role_indices) > 1 else None,
            role_switcher=AccountRoleSwitcher(),
        )
        progress = state.get("progress")
        if isinstance(progress, dict):
            runner.load_progress(progress)
            _print(
                "RESTORED_PROGRESS="
                f"role:{progress.get('current_role_index', 0)},"
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
