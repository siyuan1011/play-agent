# PlayAgent

[中文](#中文) | [English](#english)

## 中文

PlayAgent 是一个基于 Python 的 Android 模拟器自动化工具包。

- `botCore`：共享基础能力和 Python DSL 运行时
- `game_bot`：用于调试任务脚本的开发专用 GUI/CLI
- `ymjh_bot`：《一梦江湖》脚本、任务队列执行器、模板和 UI

### 项目范围

PlayAgent 通过 ADB 控制 Android 模拟器。根目录的 `launch_gui.py` 是开发调试器，用于在开发过程中加载和运行 Python 任务脚本。产品或游戏专用的脚本与 UI 位于各自的子机器人包中。

项目已移除 YAML 任务支持，任务统一使用 Python DSL 类定义。

### 快速开始

```powershell
uv venv .venv
uv sync --dev --no-install-project
```

启动开发调试器：

```powershell
uv run --no-sync python launch_gui.py
```

通过 CLI 运行 Python DSL 任务。只有在需要原始模板匹配、坐标和轮询日志时才添加 `--debug`：

```powershell
uv run --no-sync python -m game_bot.run --task src/ymjh_bot/task/QDYX_task.py [--debug]
```

启动《一梦江湖》任务队列管理器：

```powershell
uv run --no-sync python -m ymjh_bot.main
```

使用 `角色1` 至 `角色5` 复选框选择任意角色组合。角色按编号顺序执行；每个选中角色都会先完成导航和校验，再从头执行完整的已保存任务图。角色、任务和步骤位置会一起持久化，以支持断点恢复。无界面执行器支持 `--role 1 --role 3 --role 5` 这类可重复选项；兼容选项 `--roles N` 会选择前 N 个角色。

### 角色切换调试任务

在队列管理器中选择 `调试任务（等待 10 秒）` 和至少两个角色，即可测试角色切换。每次角色切换并校验成功后，该任务只等待 10 秒，然后完成并进入下一个角色；任务本身不会识图、点击或恢复游戏状态。

### DSL 示例

```python
from botCore import GameTask, step


class MyTask(GameTask):
    design_resolution = (1280, 720)
    loop_count = 1

    @step(retry=3, timeout_ms=10000)
    def click_start(self) -> bool:
        if self.find_image("templates/btn_start.png"):
            self.click()
            return True
        return False
```

### 日志

运行日志写入 `logs/`，默认保留七天：

- `events.jsonl`：结构化事件
- `shots/*.png`：可选的标注截图

默认日志级别为 INFO。只有 DEBUG 模式会输出详细的模板匹配、坐标和轮询信息。删除过期产物前可先预览：

```powershell
.\.venv\Scripts\python.exe tools/cleanup_debug_artifacts.py
.\.venv\Scripts\python.exe tools/cleanup_debug_artifacts.py --apply
```

### 测试

调试产物清理期间移除了旧测试脚本。新增测试应使用 `tests/fixtures/ymjh/` 中整理过的真机帧，不要把采集文件写入仓库根目录。

---

## English

PlayAgent is a Python-based Android emulator automation toolkit.

- `botCore`: shared foundation and Python DSL runtime
- `game_bot`: development-only GUI/CLI for debugging task scripts
- `ymjh_bot`: Yi Meng Jiang Hu scripts, queue runner, templates, and UI

### Scope

PlayAgent controls Android emulators through ADB. The root `launch_gui.py` entry point is a developer debugger for loading and running Python task scripts during development. Product- or game-specific scripts and UI live inside their own sub-bot packages.

YAML task support has been removed. Tasks are defined as Python DSL classes.

### Quick Start

```powershell
uv venv .venv
uv sync --dev --no-install-project
```

Start the development debugger:

```powershell
uv run --no-sync python launch_gui.py
```

Run a Python DSL task from the CLI. Add `--debug` only when raw template, coordinate, and polling logs are needed:

```powershell
uv run --no-sync python -m game_bot.run --task src/ymjh_bot/task/QDYX_task.py [--debug]
```

Start the Yi Meng Jiang Hu queue manager:

```powershell
uv run --no-sync python -m ymjh_bot.main
```

Use the `角色1` through `角色5` checkboxes to select any account-role combination. Roles run in numeric order, and every selected role is navigated to and verified before its complete saved task graph starts from the beginning. Role, task, and step positions are persisted together for resume. The headless runner supports repeatable selections such as `--role 1 --role 3 --role 5`; the compatible `--roles N` option selects the first N roles.

### Role-switching Debug Task

In the queue manager, select `调试任务（等待 10 秒）` and at least two roles to test role switching. After each role is selected and verified, the task waits for 10 seconds, completes, and advances to the next role. The task itself performs no image matching, clicking, or game-state recovery.

### DSL Example

```python
from botCore import GameTask, step


class MyTask(GameTask):
    design_resolution = (1280, 720)
    loop_count = 1

    @step(retry=3, timeout_ms=10000)
    def click_start(self) -> bool:
        if self.find_image("templates/btn_start.png"):
            self.click()
            return True
        return False
```

### Logs

Runtime logs are written below `logs/` and retained for seven days by default:

- `events.jsonl`: structured events
- `shots/*.png`: optional annotated screenshots

INFO is the default. Detailed template matches, coordinates, and polling output are emitted only in DEBUG mode. Preview expired artifacts before deleting them:

```powershell
.\.venv\Scripts\python.exe tools/cleanup_debug_artifacts.py
.\.venv\Scripts\python.exe tools/cleanup_debug_artifacts.py --apply
```

### Tests

The previous test scripts were removed during the debug-artifact cleanup. New tests should use the curated real-device frames under `tests/fixtures/ymjh/` instead of writing captures to the repository root.
