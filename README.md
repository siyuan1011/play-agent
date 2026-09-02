# PlayAgent

中文 | [English](README_EN.md)

PlayAgent 是一个基于 Python 的 Android 自动化工具包，提供 ADB 设备控制、OpenCV 视觉识别、Python DSL 任务运行时、调试界面和结构化运行日志。

游戏专属功能不会放在根项目文档中。《一梦江湖》任务、角色队列和使用说明请参阅 [`ymjh_bot` 中文文档](src/ymjh_bot/README.md)。

## 项目组成

| 目录 | 用途 |
|---|---|
| `src/botCore/` | ADB、视觉识别、任务基类、步骤执行器和日志等共享能力 |
| `src/game_bot/` | 面向开发者的单任务 GUI/CLI 调试器 |
| `src/ymjh_bot/` | 《一梦江湖》任务与队列应用，拥有独立文档 |
| `tests/` | 单元测试、流程测试和真机截图夹具 |

任务统一使用 Python DSL 类定义；项目不再支持 YAML 任务格式。

## 环境要求

- Python 3.10 或更高版本
- [uv](https://docs.astral.sh/uv/)
- 可从命令行调用的 ADB
- 已启用 ADB 的 Android 设备或模拟器

## 安装

```powershell
uv venv .venv
uv sync --dev
Copy-Item .env.example .env
```

`.env` 可配置默认 ADB 路径和设备序列号：

```dotenv
DEFAULT_ADB_PATH=adb
DEFAULT_ADB_SERIAL=127.0.0.1:16384
```

## 开发调试

启动任务脚本调试器：

```powershell
uv run python launch_gui.py
```

直接运行一个 Python DSL 任务：

```powershell
uv run python -m game_bot.run --task <任务文件.py> --serial <ADB序列号>
```

只有在需要查看模板匹配、坐标和轮询细节时才添加 `--debug`。

最小任务示例：

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

## 日志

每次运行都会在 `logs/` 下建立独立的 `run_*` 目录：

- `events.jsonl`：结构化事件与步骤结果
- `shots/*.png`：错误现场和可选标注截图

默认保留最近七天的运行目录。INFO 记录流程事件；DEBUG 额外记录模板匹配、点击坐标和轮询细节。

## 测试

运行完整测试集：

```powershell
uv run pytest -q
```

新增视觉测试时，应优先复用 `tests/fixtures/` 中整理过的真机帧，不要把临时截图写入仓库根目录。

## 正式包

当前正式包是 Windows x64 的 PyInstaller 目录包。在仓库根目录执行 `uv run ymjh-build-release` 即可完成测试、构建、压缩和校验；完整说明见 [`ymjh_bot` 正式包文档](src/ymjh_bot/README.md#正式包打包windows-x64)。

## 子项目文档

- [`ymjh_bot` 中文说明](src/ymjh_bot/README.md)
- [`ymjh_bot` English Guide](src/ymjh_bot/README_EN.md)
