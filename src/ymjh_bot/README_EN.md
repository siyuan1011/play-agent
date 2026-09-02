# ymjh_bot

[中文](README.md) | English | [Back to PlayAgent](../../README_EN.md)

`ymjh_bot` is PlayAgent's Yi Meng Jiang Hu task-queue application. It owns game startup and login, role switching, task orchestration, failure recovery, state persistence, and UI recognition based on real-device screenshot templates.

## Requirements

- Complete the installation in the [repository README](../../README_EN.md)
- The ADB target must be listed with the `device` state
- The game must render at the fixed `1280 × 720` resolution
- Run only one task queue per device at a time

Check connected devices:

```powershell
adb devices -l
```

To set a default device, edit the repository-level `.env` file:

```dotenv
DEFAULT_ADB_PATH=adb
DEFAULT_ADB_SERIAL=127.0.0.1:16384
```

## Graphical queue manager

Start the queue manager:

```powershell
uv run ymjh-bot
```

Equivalent module entry point:

```powershell
uv run python -m ymjh_bot.main
```

Basic workflow:

1. Select or enter an ADB target.
2. Use the `角色1` through `角色5` checkboxes to select any role combination.
3. Add tasks, arrange their order, and configure strategies for tasks that expose settings.
4. Start the queue. Roles always run in ascending numeric order, with a fresh task graph for each role.
5. Use the run log to inspect the current role, task, step, retries, cleanup actions, and final summary.

The `调试任务（等待 10 秒）` task is intended for multi-role switching checks. After a role is verified, it only waits for ten seconds; it performs no image matching, clicking, or game recovery.

## Headless runner

The headless runner loads the task order, task settings, and role selection previously saved by the GUI for that device:

```powershell
uv run python -m ymjh_bot.run_queue --serial 127.0.0.1:16384
```

Common options:

```powershell
# Temporarily select roles 1, 3, and 5; --role is repeatable
uv run python -m ymjh_bot.run_queue --serial 127.0.0.1:16384 `
  --role 1 --role 3 --role 5

# Compatibility option: select the first three roles
uv run python -m ymjh_bot.run_queue --serial 127.0.0.1:16384 --roles 3

# Restart from the task-graph origin while preserving task order and settings
uv run python -m ymjh_bot.run_queue --serial 127.0.0.1:16384 --clear-progress

# Emit detailed template, coordinate, and polling events
uv run python -m ymjh_bot.run_queue --serial 127.0.0.1:16384 --debug
```

`--adb-path <path>` is also available. Tasks cannot be selected from the headless command line; save the device's task queue in the GUI first.

## Roles, failures, and progress

- Progress consists of the role, task, and step positions.
- Pause preserves the current position; resume continues from that saved point.
- Pressing Stop is an explicit request to end the entire queue and clears the current run progress.
- A complete task flow is attempted up to three times. Task-owned safety cleanup runs after every failed attempt.
- When retries are exhausted and cleanup succeeds, the task is marked failed, the current role's remaining tasks are abandoned, and the queue advances to the next role.
- If normal cleanup fails, the task force-restarts the game and requires a verified safe main scene. A successful recovery advances to the next role; a failed recovery stops the queue and preserves progress.
- Run summaries distinguish all-success, completed-with-failures, user-stopped, and recovery-failed outcomes, with successful, failed, abandoned, and unexecuted task counts.

Per-device configuration and progress are stored at:

```text
src/ymjh_bot/.task_queue_states/<sanitized-adb-serial>.json
```

A per-serial run lock prevents the GUI and headless queue from starting duplicate runs for the same device.

## Available tasks

| Key | In-game/UI label | Purpose |
|---|---|---|
| `BPRW` | 帮派任务 | Guild tasks |
| `CGSS` | 茶馆说书 | Teahouse storytelling |
| `DEBUG` | 调试任务（等待 10 秒） | Role-switching debug wait |
| `HSLJ` | 华山论剑 | Mount Hua duels |
| `JHXS` | 江湖行商 | Jianghu trading |
| `JHYXB` | 江湖英雄榜 | Jianghu hero ranking |
| `JYPY` | 聚义平冤 | Justice-rally challenge |
| `KYRW` | 课业任务 | Coursework tasks |
| `MKSY` | 门客设宴 | Retainer banquet |
| `MRYG` | 每日一卦 | Daily fortune |
| `PZSY` | 破阵设宴 | Formation banquet |
| `RCFB` | 日常副本 | Daily dungeons |
| `SHRW` | 生活任务 | Life-skill gathering |
| `XSRW` | 悬赏任务 | Bounties |
| `ZGWX` | 坐观万象 | Meditation activity |

Mount Hua Duel exposes independent 1v1 and 3v3 strategies for first-win, fixed-count, or continuous execution. Life Tasks expose material, line-looping, and line-scope settings.

## Package layout

```text
src/ymjh_bot/
├── main.py                 # GUI entry point
├── run_queue.py            # Headless queue entry point
├── ym_game_task.py         # Shared game navigation, vision, and recovery
├── runner/                 # Queue runner, role switcher, and task factory
├── task/                   # Python DSL tasks
├── templates/              # Image-recognition templates
├── ui/                     # Queue UI and persisted state
├── lifecycle/              # Lifecycle helpers
└── app/                    # Application-layer helpers
```

To add a task, create a `*_task.py` file under `task/`, inherit from `YmGameTask`, and define a unique `task_key`, a user-facing `task_name`, and methods decorated with `@step`.

## Windows x64 release package

The current release is built from `ymjh_bot.spec` in the repository root as a **PyInstaller onedir bundle**, not a one-file executable. `ymjh-bot.exe` depends on the adjacent `_internal/` directory, so release the complete `ymjh-bot/` directory or the ZIP described below. Do not distribute the EXE alone.

Run all commands from the repository root on Windows x64 with 64-bit Python. PyInstaller `6.22.1` is locked in the project dependencies. Synchronize a fresh environment first:

```powershell
uv sync --dev
```

Build the formal release with the project command:

```powershell
uv run ymjh-build-release
```

The command runs the complete test suite, builds from `ymjh_bot.spec`, copies `.env.example`, creates the ZIP, and writes a SHA-256 file. Skip the test stage only when this exact checkout has already passed the complete suite:

```powershell
uv run ymjh-build-release --skip-tests
```

The spec collects every `ymjh_bot.task` module and includes `templates/` and `task/` as runtime data. The GUI is built in windowed mode without a console. The outputs are:

```text
build/release/ymjh_bot/                  # PyInstaller intermediates; do not release
dist/release/ymjh-bot/                   # Runnable directory; keep it intact
└── ymjh-bot.exe
dist/release/ymjh-bot-windows-x64.zip    # Formal release archive
dist/release/ymjh-bot-windows-x64.zip.sha256
```

ADB is not bundled, and development logs and persisted queue progress are not included. The project command copies only the public `.env.example`; it never copies the repository's local `.env`, which prevents a developer-machine path or device serial from leaking into the release.

Before publishing, extract the ZIP into an empty directory that contains no source checkout, then complete this acceptance check:

1. The archive expands to a top-level `ymjh-bot/` directory containing `ymjh-bot.exe`, `.env`, and `_internal/`.
2. Start `ymjh-bot.exe` and verify that the queue UI renders. This build has no console; inspect runtime information in the UI and under `logs/`.
3. Put ADB on `PATH`, or configure its path and device serial through `.env` or the UI, and verify the target connects.
4. Run one screenshot or debug action, then run `调试任务（等待 10 秒）` with two roles to verify task startup, log output, and role switching.
5. Compare the release against the generated `.sha256` file:

```powershell
Get-FileHash `
  -LiteralPath dist\release\ymjh-bot-windows-x64.zip `
  -Algorithm SHA256

Get-Content `
  -LiteralPath dist\release\ymjh-bot-windows-x64.zip.sha256
```

For every formal release, archive the freshly generated PyInstaller directory first, then extract and test it in a different empty directory. Do not run `dist/release/ymjh-bot/ymjh-bot.exe` before archiving that directory, or runtime logs and persisted queue state may leak into the release. Re-run PyInstaller whenever source code, templates, or dependencies change.

## Logs and diagnostics

Queue logs are grouped by device and run:

```text
logs/<sanitized-adb-serial>/run_<timestamp>/
├── events.jsonl
└── shots/
```

For a failure, first inspect the last failed step, task-retry events, and role-advance events in `events.jsonl`, then open the referenced image under `shots/`. Screenshots are failure evidence; normal image matching does not write every captured frame to disk.

## Tests

Run the complete suite:

```powershell
uv run pytest -q
```

Common focused suites:

```powershell
uv run pytest tests/test_multi_role_queue.py tests/test_multi_role_gui.py -q
uv run pytest tests/test_rcfb_sidebar_tracker.py tests/test_xsrw_task_flow.py -q
uv run pytest tests/test_task_sidebar_state.py tests/test_bprw_task_flow.py -q
```

Tests requiring a real ADB target should use the `integration` marker. Ordinary tests must not depend on the current emulator state.
