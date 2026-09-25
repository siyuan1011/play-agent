# ymjh_bot 任务开发规范

本文件适用于 `src/ymjh_bot/` 及其子目录，补充[仓库根规范](../../AGENTS.md)。根规范中的中文变量注释、改动范围、测试和提交约定在此继续适用。项目使用说明见 [README](README.md)；本文关注 Agent 如何构建和维护任务。

## 模块职责与任务发现

| 路径 | 职责 |
| --- | --- |
| `ym_game_task.py` | `YmGameTask` 共享游戏基类，封装启动、导航、状态检测、交互与恢复 |
| `task/` | 具体 Python DSL 任务及任务间共享的业务辅助逻辑 |
| `templates/` | 通用游戏模板与各任务模板，不放临时截图 |
| `runner/` | `TaskQueueRunner`、`AccountRoleSwitcher` 和任务实例工厂 |
| `ui/` | 队列 GUI、任务设置、进度与设备运行锁持久化 |
| `main.py`、`run_queue.py` | 正式 GUI 与无界面队列入口 |
| `build_release.py` | Windows x64 发布构建与打包流程 |

新增游戏交互任务放在 `task/<名称>_task.py`，继承 `YmGameTask`，从 `botCore` 导入 `step` 等 DSL API。设置唯一且稳定的 `task_key`、中文 `task_name`，按需设置 `task_description`，用 `@step` 标识步骤。

GUI 和队列 CLI 扫描 `task/*_task.py`，跳过以下划线开头的文件，并经 `load_task_class()` 查找该文件内定义的第一个非抽象任务类。每个任务文件只放一个可加载的具体任务类；公共辅助基类使用 `__abstract_task__ = True`。设置 `task_visible = False` 可从队列可选列表隐藏任务，但不是禁止直接加载。

现有 `DEBUG` 任务只等待十秒以观察角色切换，直接继承 `GameTask`，无需游戏识图、启动和恢复。保留这种无游戏交互任务的例外。

## YmGameTask 能力速查

编写任务前先阅读 [ym_game_task.py](ym_game_task.py) 的对应方法、调用方和相关测试。下面列的是已有能力入口；实际参数、返回值和副作用以源码为准，不能仅根据方法名推断行为。

| 能力 | 常用方法或钩子 | 使用场景与注意点 |
| --- | --- | --- |
| 启动登录 | `ensure_game_started()`、`is_game_main_ready()`、`detect_login_state()` | 确认前台及主界面，按需启动应用、推进登录和清理；不要在每个任务中复制登录流程 |
| 启动初始化 | `before_start()`、`on_start()`、`reset_startup_state()`、`after_startup_panel_close()` | 复用统一启动清理，在扩展钩子中重置任务状态或处理任务专属弹窗 |
| 重试与恢复 | `before_retry()`、`after_retry_recovery()`、`try_escape_stuck()`、`recover_after_cleanup_failure()` | 重试时处理省电、脱困与血量；常规清理失败后强制重启并验证安全主界面 |
| 通用面板 | `close_all_panels()`、`collapse_chat_if_open()`、`collapse_emotion_panel_if_open()`、`confirm_center_modal_ok_if_visible()` | 关闭遮挡界面、折叠聊天或表情、确认明确可识别的弹窗 |
| 活动导航 | `ensure_top_shortcuts_expanded()`、`open_activity_panel()`、`open_activity_category()`、`ensure_bangpai_activity_tab()` | 先恢复活动入口并验证面板，再切换分类，避免盲点分类坐标 |
| 任务侧栏 | `ensure_task_sidebar_open()`、`switch_task_panel()` | 验证紧凑任务侧栏，切换“任务 / 江湖 / 奇遇”，处理全屏误入和激活状态 |
| 单次识别 | `find_image_once()`、继承的 `find_image()` | 一次截图检查；结果用于当前判断，后续识别会更新缓存的匹配中心 |
| 等待与点击 | `wait_find_image_in_roi()`、`click_template_if_available()`、继承的 `wait_image_appear()` / `wait_image_missing()` | 限定 ROI、等待出现或稳定消失、识别成功后点击；检查布尔结果 |
| 地图与寻路 | `return_to_safe_zone()`、`ensure_local_map_open()`、`ensure_world_map_open()`、`wait_auto_pathfinding_started()`、`wait_auto_pathfinding()` | 验证地图切换与寻路开始，等待寻路及其后的过图稳定结束 |
| 组队 | `open_team_panel()`、`open_quick_team_panel()`、`create_team()`、`quick_team()`、`wait_for_team_members()`、`leave_team()` | 复用队伍入口、目标选择、人数等待、匹配和离队逻辑 |
| 运行状态 | `check_runtime_status()`、`wake_from_power_saving_if_needed()`、`detect_health_ratio()`、`recover_health_if_needed()` | 按需处理省电、自动寻路、过图和血量，避免每个任务自行拼装状态检查 |
| 对话与操作 | `click_dialog_next_if_visible()`、`drain_dialog_next()`、`walk()`、`auto_battle()`、`turn_battle_skill_page()` | 推进可识别对话，执行已有移动和战斗操作；保留各方法的场景前置检查 |
| 日志与现场 | `_log()`、`_debug()`、`save_debug_screenshot()` | 记录流程、识图细节及失败现场，使异常能关联截图定位原因 |

`check_runtime_status()` 接受 `power`、`health`、`finding`、`loading`，不传检测项时检查全部。执行顺序为省电处理、所选过渡状态等待、血量恢复，不随参数排列变化；返回 `False` 时由任务决定重试或失败，用户停止异常继续传播。血量无法识别沿用当前恢复方法的处理约定，不能将返回成功解释为已测得满血。

## 复用与扩展原则

1. 先确认 `YmGameTask` 是否已覆盖需求，再看已有任务如何调用。优先组合现有方法，不重复实现登录、关面板、活动导航、组队、寻路等待或通用恢复循环。
2. 优先通过类属性和扩展钩子表达任务差异，如 `RETURN_TO_SAFE_ZONE_ON_START`、`LEAVE_TEAM_ON_START`、`STARTUP_CLOSE_SETTLE_WAIT_MS`、`reset_startup_state()` 和 `after_startup_panel_close()`。不要复制整个 `on_start()` 仅修改其中一个动作。
3. 必须覆盖生命周期方法时，阅读父类实现并保留必要的 `super()` 调用和执行顺序。默认 `before_start()` 确保游戏就绪，`on_start()` 执行场景清理及血量预检；当前 `before_step()` 不会每步自动补血，任务需要时显式调用状态封装。
4. 多个任务共享的游戏操作优先补充到 `YmGameTask`；只服务单个任务的流程保留在该任务内，少数同类任务的专属业务辅助可放在 `task/`。跨游戏通用能力才下沉至 `botCore`，不把特定活动规则塞入基础层。
5. 只有现有封装确实无法表达需求时，才增加底层调用或辅助方法；说明差异，尽可能组合底层公共能力，并覆盖现有调用方的回归场景。不要为了绕过异常而复制一份略有不同的通用流程。

步骤重试与完整任务重试不同：步骤重试不会重新执行 `on_start()`，完整任务重试会重新进行任务启动。任务专属状态应在正确的启动/重试钩子中重置，防止上一轮计数或完成标记污染新一轮执行。

## 视觉、坐标与失败语义

- 游戏画面固定为 `1280×720`。`YmGameTask.click_point()` 和 `scale_roi()` 不进行运行时缩放；点使用 `(x, y)`，ROI 使用 `(x, y, width, height)`，单位均为像素。不要套用通用 `GameTask` 的自动缩放假设，也不要把地图世界坐标当成屏幕点击坐标。
- 通用模板和常量优先复用基类；任务专属模板通过 `TEMPLATES_DIR` 或文件位置构造路径，不依赖进程工作目录。新增坐标、ROI、阈值和时间常量逐项添加中文注释，说明用途与单位。
- `find_image()`、`find_image_once()` 和图像等待会影响最后匹配结果。依赖 `self.click()` 点击匹配中心时，应紧接确认成功的识别，避免中间另一轮识别改变点击目标。
- `wait_image_appear()` 的 `appear_mode="total"` 是累计命中，`"consecutive"` 是连续命中；要求连续稳定时显式指定。`wait_image_missing()` 使用连续缺失计数。传入 `screenshot` 会重复使用同一帧，等待真实界面变化时应让方法重新截图。
- 同一时刻需要判断多个标记时，复用支持传入截图的接口进行同帧判断；不要为了复用而向不支持该参数的方法传参。新模板优先来自真实截图，补充正例、反例及易混淆场景。
- 布尔返回值必须检查，失败时返回 `False` 或抛出包含上下文的异常；成功返回 `None` 的导航方法不能写成 `if not self.open_activity_panel(...)`。具体返回契约需读源码确认。
- 捕获普通异常时，先让 `StepStopException` 和步骤跳转异常继续传播。不要把用户停止、面板无法确认或识别超时处理成任务成功。
- 侧栏未确认的 `TaskSidebarStateError` 不等同于“任务不存在”。`ActivityEntryUnavailableError` 需要交给现有队列活动入口恢复流程；不要局部吞掉或重复强制重启。
- 优先使用带停止响应的 `self.wait()` 和公共等待接口；自定义循环设置退出条件，通常设置有限截止时间。即便 `@step(timeout_ms=...)` 已配置，执行器也不能强制打断函数内部的无限循环；持续任务应明确允许持续的配置并保持可停止。
- 任务失败清理通过 `cleanup_after_failure()` 处理任务自身外部状态；基类默认实现为空，任务有专属队伍或界面状态时按需实现。常规清理无法确认安全时保留失败，让队列调用 `recover_after_cleanup_failure()`，不要假装清理成功。

## 新任务最小示例

下面示例展示共享启动、状态检查和活动导航的组合。任务文件名遵守 `*_task.py`，使用前替换示例的唯一键和名称；示例只打开并关闭活动分类，不代表完成某个实际玩法。

```python
from botCore import step
from ymjh_bot.ym_game_task import YmGameTask


class ExampleTask(YmGameTask):
    """演示复用游戏共享能力的任务。"""

    task_key = "EXAMPLE"  # 任务稳定唯一标识，实际任务需要替换。
    task_name = "活动导航示例"  # 队列中显示的中文任务名称。
    task_description = "检查状态并打开江湖活动分类"  # 用户可见的任务用途说明。

    @step(retry=1, timeout_ms=60_000)
    def open_jianghu_activity(self) -> bool:
        """检查状态后打开活动分类，并清理示例面板。

        参数：
            self：由 runner 初始化并注入设备依赖的当前任务实例。
        """
        status_ready = self.check_runtime_status(
            "power", "finding", "loading", timeout_ms=10_000
        )  # 省电与过渡状态是否已通过检查。
        if not status_ready:
            return False
        self.open_activity_category("江湖")
        self.close_all_panels(timeout_ms=3000)
        return True
```

保持 `@step(...)` 紧邻步骤定义，便于当前 DSL 按源码顺序发现步骤。需要额外任务设置时，同时接入设置归一化、GUI 和 `create_task_instances()`，保证 GUI 与 CLI 使用一致配置；通用单任务加载会无参数实例化任务，新增构造参数应提供合理默认值。

## 队列、状态与角色隔离

- `TaskQueueRunner` 管理顺序执行和完整任务恢复，`AccountRoleSwitcher` 管理角色切换，`create_task_instances()` 为每个角色创建全新的配置化任务实例。任务不要自行接管跨角色调度，也不要将角色进度放在共享可变类属性中。
- 界面/CLI 的角色编号为 1～5，内部角色索引从零开始，选中角色按编号升序运行。进度中的 `current_role_index` 是选中角色列表中的位置，不是角色编号；另外两个维度为任务位置和步骤位置。
- 配置与进度按设备保存在 `.task_queue_states/<安全化ADB序列号>.json`，沿用现有保存、归一化及旧状态兼容逻辑。任务键影响已保存的配置，变更键或设置结构时必须考虑兼容。
- GUI 点击“开始”创建全新运行并清除旧进度；暂停保留位置，继续从暂停位置恢复；用户停止结束队列并清除本次进度。CLI 默认读取已保存进度，`--clear-progress` 清除断点后从头运行。
- 设备序列号运行锁用于防止 GUI/CLI 同时控制同一设备，不绕过锁或随意删除其他运行实例的状态。
- 普通完整任务最多尝试三次，失败后由队列调用任务清理；耗尽后按恢复结果放弃当前角色后续任务并推进角色，或停止队列保留进度。活动入口异常另有一次专门恢复路径，维护时保留现有结果摘要和推进语义。
- 源码运行的队列日志位于仓库 `logs/<安全化ADB序列号>/run_*/`，查看 `events.jsonl` 及其引用的 `shots/`。不要提交本机设备配置、运行锁、队列进度或临时日志。

## 验证与交付

命令从仓库根目录执行。按改动选择对应测试；以下均为当前存在的测试文件，不需要启动游戏来做普通流程验证。

| 改动领域 | 专项命令 |
| --- | --- |
| 图像等待 | `uv run pytest tests/test_image_waits.py -q` |
| 状态、省电与血量 | `uv run pytest tests/test_runtime_status.py tests/test_power_saving_detection.py tests/test_health_lifecycle.py -q` |
| 启动与重试 | `uv run pytest tests/test_task_retry_startup.py tests/test_activity_task_stability.py -q` |
| 活动入口恢复 | `uv run pytest tests/test_top_shortcuts_recovery.py tests/test_task_queue_activity_entry_recovery.py -q` |
| 队伍面板 | `uv run pytest tests/test_team_panel.py -q` |
| GUI 全新开始 | `uv run pytest tests/test_queue_fresh_start.py -q` |
| 生活任务与挖矿 | `uv run pytest tests/test_shrw_task_flow.py tests/test_mining_flow.py tests/test_mining_ui.py -q` |
| 其他具体任务 | 选择 `tests/` 中对应流程测试，例如 `test_mksy_task_flow.py`、`test_xsrw_task_flow.py` |
| 全部测试 | `uv run pytest -q` |

共享封装变更应覆盖成功、目标缺失/超时、重试恢复和用户停止，并检查相关任务仍使用统一接口。队列改动关注每角色新实例、角色/任务/步骤推进、配置持久化和暂停继续。视觉变更优先复用真实帧；实机验证另行记录设备、分辨率、步骤和截图证据。

文档变更检查相对链接、方法名、命令和示例语法即可。交付说明执行过的验证与未执行的真机检查，不把截图夹具测试描述为真机运行成功。
