"""Development CLI for running Python DSL task scripts.

Usage:
    # 运行 Python DSL 任务
    python -m game_bot.run --task src/ymjh_bot/task/QDYX_task.py

    # 指定设备
    python -m game_bot.run --task src/ymjh_bot/task/QDYX_task.py --serial 127.0.0.1:5555
"""

from __future__ import annotations

import argparse
from pathlib import Path

from botCore import ADBClient, DSLTaskRunner, GameTask, RunLogger, VisionEngine

from .task_loader import load_task_definition


def main() -> int:
    parser = argparse.ArgumentParser(description="Development runner for Python DSL task scripts")
    parser.add_argument("--task", "-t", required=True, help="Python task file (.py)")
    parser.add_argument("--adb", default="adb", help="ADB path")
    parser.add_argument("--serial", "-s", help="Device serial (overrides task config)")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    args = parser.parse_args()

    task_path = Path(args.task)
    if not task_path.exists():
        print(f"Error: Task file not found: {task_path}")
        return 1

    print(f"Loading task: {task_path}")

    try:
        task = load_task_definition(task_path)
    except Exception as e:
        print(f"Error loading task: {e}")
        return 1

    if not (isinstance(task, type) and issubclass(task, GameTask)):
        print(f"Error: Unknown task type: {type(task)}")
        return 1

    print(f"Executing Python DSL task: {task.__name__}")

    task_instance = task()
    adb = ADBClient(adb_path=args.adb, serial=args.serial)
    vision = VisionEngine()
    logger = RunLogger()
    runner = DSLTaskRunner(
        task_instance,
        adb,
        vision,
        logger=logger,
        event_callback=lambda msg: print(msg),
        verbose=args.debug,
    )

    try:
        results = runner.run()
        success_count = sum(1 for r in results if r.success)
        print(f"\nFinished: {success_count}/{len(results)} steps succeeded")
        return 0 if success_count == len(results) else 1
    except KeyboardInterrupt:
        runner.stop()
        print("\nStopped by user")
        return 130
    except Exception as e:
        print(f"Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
