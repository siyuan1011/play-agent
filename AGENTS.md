# PlayAgent 项目开发规范

本文件适用于整个仓库。修改 `src/ymjh_bot/` 下的内容时，同时遵守该目录的 [AGENTS.md](src/ymjh_bot/AGENTS.md)；子目录规则细化对应业务，上级通用规则继续适用。用户当前明确要求优先于本文约定。

## 项目能力与架构

PlayAgent 是基于 Python 3.10+ 的 Android 自动化工具包，使用 uv 管理环境和依赖。PySide6 提供桌面界面，OpenCV/NumPy 提供图像处理，ADB 提供设备交互，python-dotenv 用于读取本地环境配置。

| 层级 | 能力与职责 |
| --- | --- |
| `botCore` 基础层 | ADB 设备发现、连接、截图、点击、滑动、Shell 和应用启动；模板匹配、二值化匹配及 ROI 识别；坐标缩放、随机偏移；Python DSL、任务加载、步骤执行、日志与截图 |
| `game_bot` 调试层 | 面向开发者的单任务 GUI/CLI，使用公共加载器与 `DSLTaskRunner` 调试 Python 任务 |
| `ymjh_bot` 游戏应用层 | 《一梦江湖》任务、共享游戏操作、角色切换、队列编排、状态持久化、正式 GUI/CLI 与发布构建 |

依赖方向为 `game_bot / ymjh_bot → botCore`。`botCore` 是唯一基础层，不反向依赖具体游戏；游戏专属导航、模板和规则放在对应子 bot 中。任务统一使用 Python DSL，不恢复已删除的 YAML 任务格式、旧 `yamlBot` 或 `dslBot` 实现。

运行链路：

1. GUI/CLI 加载任务类并创建任务实例。公共加载入口为 `load_task_class()` 和 `load_task_instance()`。
2. runner 检查设备和截图分辨率，通过 `GameTask.setup()` 注入 ADB、`VisionEngine`、`RunLogger` 和事件回调。
3. 按 runner 的启动条件执行 `before_start()`、`on_start()`，再执行带 `@step` 的方法；具备收尾钩子的任务由 runner 调用 `on_finish()`。
4. 单任务 `DSLTaskRunner` 与游戏 `TaskQueueRunner` 共用 `DslStepExecutor` 和跳转解析逻辑。游戏队列额外管理角色、完整任务重试、暂停继续、进度及失败恢复；两种 runner 的失败推进规则不能混为一谈。
5. 执行产生 `ExecutionResult`、界面/控制台事件和运行日志。任务通过等待和轮询中的停止检查配合 runner 响应控制请求。

DSL API 优先从 `botCore` 公共出口导入，例如 `GameTask`、`step`、`StepJumpException` 和 `StepStopException`。`@step` 支持重试、超时、启用状态与步骤间隔；`jump_to*()` 用于步骤跳转。步骤返回 `None` 或 `True` 表示成功，`False` 或普通异常进入失败处理；跳转和停止异常具有独立语义，不得被普通异常处理吞掉。

步骤超时由执行器在尝试边界检查，不能强制中断任意阻塞代码。任务中的等待优先使用 `self.wait()` 或已有图像等待方法；自定义循环必须处理停止并明确结束条件，通常应设置有限超时。不要用长时间 `time.sleep()` 代替可响应停止的等待。

## 项目结构与归属

| 路径 | 归属与用途 |
| --- | --- |
| `src/botCore/` | ADB、视觉、坐标、任务基类、加载器、执行器、runner、日志和运行产物清理 |
| `src/game_bot/`、`launch_gui.py` | 开发调试 GUI/CLI 及快捷入口，不承载正式游戏队列 UI |
| `src/ymjh_bot/` | 游戏共享基类、任务、模板、队列 runner、角色切换、UI 与构建入口 |
| `tests/`、`tests/fixtures/` | 单元与流程测试、整理后的真实截图夹具；普通测试不依赖当前模拟器状态 |
| `docs/`、`docs/assets/` | 架构、DSL、任务流程及验证记录，文档使用的静态素材 |
| `pyproject.toml`、`uv.lock` | 依赖、命令入口、pytest 配置和依赖锁定 |
| `.env.example`、本地 `.env` | 公开配置示例与本机 ADB 配置；不要将本机私有配置混入提交或发布产物 |
| `ymjh_bot.spec`、`build/`、`dist/` | PyInstaller 配置、中间产物和发布包；不手工修改生成结果代替源码修复 |
| `logs/`、`artifacts/` | 运行或验证产物；其中临时输出不作为源码，不默认加入提交 |
| `.venv/`、各类缓存和 `*.egg-info/` | 本地环境、缓存与生成元数据，不作为功能实现位置 |

详细背景见 [README](README.md)、[项目结构说明](docs/PROJECT_STRUCTURE.md)、[DSL 指南](docs/DSL_GUIDE.md) 和 [ymjh_bot 说明](src/ymjh_bot/README.md)。引用其中命令、路径和 API 前，应核对当前源码；发现文档过时时，不复制失效内容。

## 常用命令与验证

以下命令均从仓库根目录运行。依赖同步使用 `uv sync --dev`。首次配置时，仅在本地 `.env` 不存在的情况下从 `.env.example` 复制，避免覆盖已有配置。

| 用途 | 命令 |
| --- | --- |
| 同步开发依赖 | `uv sync --dev` |
| 开发调试 GUI | `uv run python launch_gui.py` 或 `uv run python -m game_bot.main` |
| 单任务 CLI | `uv run python -m game_bot.run --task <任务文件.py> --serial <ADB序列号>` |
| 游戏队列 GUI | `uv run ymjh-bot` 或 `uv run python -m ymjh_bot.main` |
| 游戏队列 CLI | `uv run python -m ymjh_bot.run_queue --serial <ADB序列号>` |
| 普通自动化测试 | `uv run pytest -q -m "not integration"` |
| 完整测试集 | `uv run pytest -q` |
| Windows x64 正式包 | `uv run ymjh-build-release` |

尖括号内容需要替换为实际值。单任务 CLI 的 ADB 路径选项为 `--adb`，队列 CLI 为 `--adb-path`；排查视觉细节时才添加 `--debug`。队列 CLI 读取 GUI 为对应设备保存的任务配置，不通过命令行选择任务。

执行设备任务前，确认 ADB 可调用、设备已启用 ADB，并通过 `adb devices -l` 确认状态为 `device`。同一设备同一时间只运行一条队列。实际启动任务、恢复游戏和角色切换会操作设备，不作为普通文档或静态检查的默认步骤。

根据改动选择现有专项测试；公共执行、视觉或生命周期变化需要覆盖相关调用方，必要时运行完整测试集。真机测试使用 `integration` 标记并单独说明设备与结果。纯文档变更检查内容、链接、代码示例和 diff 即可，不为此新增业务测试或启动模拟器。

发布使用 Windows x64 和 64 位 Python。构建命令会执行测试、生成 PyInstaller 目录包、ZIP 和 SHA-256 文件；发布整个目录包或 ZIP，不能只分发 EXE。其余发布验收要求见子项目 README。

## 中文变量注释规范

后续新增或修改的每个变量都必须具有对应中文说明。该规则适用于代码与文档代码示例，不要求为未触及的历史代码集中补注释。

- 覆盖模块常量、类属性、实例属性、数据类字段、函数参数、局部变量、循环变量、解包变量及异常变量。元组解包与推导式中的每个名称也要能对应到说明。
- 常量、字段和局部变量在声明或首次赋值处使用中文行前或行尾注释；参数可在函数文档字符串中逐项说明。`self`、`cls` 等约定参数也可在文档字符串中说明其所指对象。
- 注释说明变量的用途和业务含义；涉及时间、坐标、阈值、索引或可选值时，按需注明单位、坐标系、范围、是否从零开始以及 `None` 的含义。
- 类型标注和英文变量名不能替代中文说明。避免只重复名称的无信息注释；一条注释解释多个变量时，必须逐一标明对应关系。
- 同一变量含义不变的普通重复赋值无需重复注释；修改用途、单位或取值约定时同步更新说明。只修改某个函数，不要求顺便重写该文件所有历史注释。

示例：

```python
def remaining_wait_ms(timeout_ms: int, elapsed_ms: int) -> int:
    """计算剩余等待毫秒数，最小为零。

    参数：
        timeout_ms：允许等待的总时长，单位为毫秒。
        elapsed_ms：已等待的时长，单位为毫秒。
    """
    remaining_ms = max(0, timeout_ms - elapsed_ms)  # 剩余可等待时长，单位为毫秒。
    return remaining_ms
```

## Agent 工作约定

- 默认使用简洁中文沟通。先阅读目标文件、相关调用点与测试，优先用 `rg` 搜索代码和文件，再决定实现方式。
- 优先复用已有接口和共同执行路径；修复根因，保持命名与代码风格一致。不要为局部需求复制一套 ADB、视觉、runner 或游戏恢复逻辑。
- 开工时查看 Git 状态，保护用户已有修改。只做任务需要的局部改动，不覆盖未提交工作，不顺手重构、批量格式化或清理无关文件。
- 缺失信息先从源码、配置与测试中确认；只对影响实现的未知需求提出问题。对于已明确授权的工作继续完成，不反复要求确认。
- 排查运行问题先看 `events.jsonl` 的失败步骤、重试与恢复记录，再查看日志引用的截图。使用已有日志接口保留上下文，常规流程写 INFO，识图分数、坐标和轮询细节写 DEBUG。
- `RunLogger` 默认保留最近七天的运行目录。需要长期保留的验证证据应整理至测试夹具或文档素材，并说明用途；不要把临时截图写到仓库根目录。
- 新增视觉回归优先使用 `tests/fixtures/` 中的真实帧，覆盖目标存在、目标缺失及易误识别的场景。设备不可用时如实报告未执行真机验证，不推断验证通过。
- 交付前检查本次 diff、链接或接口引用，并运行与改动相称的验证。最终说明修改内容、验证结果和确实存在的未完成项；不得虚构命令输出或测试成功。
- 用户要求提交时，遵守仓库配置并默认采用中文 Conventional Commits：`<type>(<scope>): <中文动宾摘要>`。默认类型为 `feat`、`fix`、`docs`、`style`、`refactor`、`perf`、`test`、`build`、`ci`、`chore`、`revert`；标题通常不超过 72 字符且不加句号。破坏性变更使用 `!` 与正文 `BREAKING CHANGE:`，无关主题建议拆分提交。
