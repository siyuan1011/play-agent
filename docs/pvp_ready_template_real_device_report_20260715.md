# 论剑/英雄榜准备模板真机测试报告（2026-07-15）

## 测试环境

- ADB：`127.0.0.1:16416`
- 设备：`PGT_AN10`，游戏包 `com.netease.wyclx`
- 分辨率：`1280x720`
- 匹配算法：项目 `VisionEngine`，`cv2.TM_CCOEFF_NORMED`
- 运行阈值：`0.85`
- 英雄榜 ROI：`(520, 40, 240, 120)`
- 华山论剑 ROI：`(520, 35, 240, 120)`

## 测试方法

1. 在真机上分别进入江湖英雄榜与华山论剑 1v1 匹配。
2. 准备按钮出现后连续采集 10 帧，覆盖发光边框的多个闪烁相位。
3. 对每帧使用项目实际 `VisionEngine` 比较 `text_ready.png` 与原整按钮模板。
4. 另取匹配面板和战斗画面作为负样本，检查小文字模板是否误报。

## 动态匹配结果

| 场景 / 模板 | 最低分 | 平均分 | 最高分 | `>=0.85` |
| --- | ---: | ---: | ---: | ---: |
| 英雄榜 / `text_ready.png` | 0.9715 | 0.9791 | 0.9828 | 10/10 |
| 英雄榜 / 原 `btn_jhyxb_ready.png` | 0.4641 | 0.6032 | 0.7923 | 0/10 |
| 华山 / `text_ready.png` | 0.9933 | 0.9942 | 0.9947 | 10/10 |
| 华山 / 原 `btn_hslj_ready.png` | 0.5401 | 0.6723 | 0.8965 | 1/10 |
| 华山 / 原备用 `btn_hslj_ready_battle.png` | 0.5893 | 0.7659 | 0.9780 | 3/10 |

原模板包含发光边框和大面积半透明背景，分数随闪烁相位明显变化。`text_ready.png` 仅保留 50x23 的“准备”文字区域，在两个玩法的所有动态帧中都稳定通过阈值，因此不需要再次裁剪。

## 负样本结果

| 场景 | `text_ready.png` 分数 |
| --- | ---: |
| 英雄榜匹配面板 | 0.2415 |
| 英雄榜战斗中 | 0.2530 |
| 华山匹配面板 | 0.2027 |
| 华山战斗中 | 0.1970 |

负样本距离 0.85 阈值至少 0.597，未发现误报风险。

## 截图证据

- [英雄榜闪烁低相位](assets/real_device/pvp/jhyxb_ready_low.webp)（旧模板 0.4641、新模板 0.9807）
- [英雄榜闪烁高相位](assets/real_device/pvp/jhyxb_ready_high.webp)（旧模板仍仅 0.7923、新模板 0.9826）
- [华山准备页首次命中](assets/real_device/pvp/hslj_ready_first.webp)（新模板 0.9944，中心 `(640, 88)`）
- [华山旧备用模板高相位](assets/real_device/pvp/hslj_ready_high.webp)
- [华山点击准备后进入结算](assets/real_device/pvp/hslj_ready_click_success.webp)
- [英雄榜旧逻辑漏过准备后的超时现场](assets/real_device/pvp/jhyxb_ready_timeout.webp)

原始连续采集帧已在提取上述高、低相位和结果证据后清理。

## 实现与回归

- 江湖英雄榜 `BTN_JHYXB_READY` 已改用 `text_ready.png`。
- 华山论剑 `BTN_HSLJ_READY_TEMPLATES` 已改为仅使用 `text_ready.png`。
- ROI 与 0.85 阈值保持不变。
- 回归命令：`uv run pytest tests/test_jhyxb_task.py tests/test_hslj_task.py tests/test_vision_template.py`
- 结果：`95 passed`。

真机华山探针在准备页首次检测分数为 0.9944、中心为 `(640, 88)`。两次同进程匹配由服务器在进入准备页前返回可匹配面板，任务正确返回 `hslj_panel`，没有产生准备按钮误点击；最终一次同进程重试成功匹配，新模板以 0.9923 命中 `(640, 88)`，日志输出“点击华山论剑准备按钮”，实际点击后返回 `READY_STATE=ready`。

## 结论

`text_ready.png` 对英雄榜和华山论剑都明显优于原整按钮模板，能够规避闪烁边框造成的漏检，且在面板和战斗负样本上保有充足阈值余量。本次已统一替换两个玩法的准备识别模板。
