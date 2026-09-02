# PlayAgent

[中文](README.md) | English

PlayAgent is a Python-based Android automation toolkit. It provides ADB device control, OpenCV-powered visual recognition, a Python DSL task runtime, development tools, and structured run logs.

Game-specific behavior is documented outside the repository-level guide. For Yi Meng Jiang Hu tasks, role queues, and operating instructions, see the [`ymjh_bot` English guide](src/ymjh_bot/README_EN.md).

## Repository layout

| Directory | Purpose |
|---|---|
| `src/botCore/` | Shared ADB, vision, task, step-execution, and logging primitives |
| `src/game_bot/` | Developer-only GUI and CLI for debugging one task script |
| `src/ymjh_bot/` | Yi Meng Jiang Hu tasks and queue application, with separate documentation |
| `tests/` | Unit tests, flow tests, and curated real-device fixtures |

Tasks are defined as Python DSL classes. YAML task definitions are no longer supported.

## Requirements

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/)
- ADB available from the command line
- An Android device or emulator with ADB enabled

## Installation

```powershell
uv venv .venv
uv sync --dev
Copy-Item .env.example .env
```

Use `.env` to configure the default ADB executable and device serial:

```dotenv
DEFAULT_ADB_PATH=adb
DEFAULT_ADB_SERIAL=127.0.0.1:16384
```

## Development and debugging

Start the task-script debugger:

```powershell
uv run python launch_gui.py
```

Run one Python DSL task directly:

```powershell
uv run python -m game_bot.run --task <task-file.py> --serial <adb-serial>
```

Add `--debug` only when detailed template matches, coordinates, and polling events are needed.

Minimal task example:

```python
from botCore import GameTask, step


class MyTask(GameTask):
    design_resolution = (1280, 720)

    @step(retry=3, timeout_ms=10_000)
    def click_start(self) -> bool:
        if not self.find_image("templates/btn_start.png"):
            return False
        self.click()
        return True
```

## Logs

Each run creates an isolated `run_*` directory below `logs/`:

- `events.jsonl`: structured events and step results
- `shots/*.png`: failure evidence and optional annotated screenshots

Run directories are retained for seven days by default. INFO records flow events, while DEBUG adds template-match, click-coordinate, and polling details.

## Tests

Run the complete test suite:

```powershell
uv run pytest -q
```

New visual tests should reuse curated real-device frames under `tests/fixtures/`. Do not write temporary captures to the repository root.

## Release package

The current release is a PyInstaller directory bundle for Windows x64. Run `uv run ymjh-build-release` from the repository root to test, build, archive, and checksum it. See the [`ymjh_bot` release packaging guide](src/ymjh_bot/README_EN.md#windows-x64-release-package) for details.

## Subproject documentation

- [`ymjh_bot` 中文说明](src/ymjh_bot/README.md)
- [`ymjh_bot` English Guide](src/ymjh_bot/README_EN.md)
