from pathlib import Path

from botCore import ADBClient, RunLogger, VisionEngine
from ymjh_bot.runner.account_role_switcher import AccountRoleSwitcher
from ymjh_bot.runner.task_queue_runner import TaskQueueRunner
from ymjh_bot.task.XSRW_task import XSRWTask
from ymjh_bot.ui.task_queue_state import serial_run_lock


SERIAL = "127.0.0.1:16384"


def make_tasks():
    return [XSRWTask()]


def main() -> None:
    lock = serial_run_lock(
        Path("src/ymjh_bot/.task_queue_states"),
        SERIAL,
    )
    if not lock.acquire():
        raise RuntimeError(f"{SERIAL} 已有运行中的任务队列")
    try:
        logger = RunLogger(base_dir=Path("logs/live_xsrw_16384"))
        print(f"LIVE_RUN_DIR={logger.run_dir}", flush=True)
        runner = TaskQueueRunner(
            make_tasks(),
            ADBClient(adb_path="adb", serial=SERIAL),
            VisionEngine(),
            logger=logger,
            event_callback=lambda message: print(message, flush=True),
            role_indices=[0, 1],
            task_factory=make_tasks,
            role_switcher=AccountRoleSwitcher(),
        )
        runner.run()
        print(f"LIVE_SUMMARY={runner.get_run_summary()}", flush=True)
    finally:
        lock.release()


if __name__ == "__main__":
    main()
