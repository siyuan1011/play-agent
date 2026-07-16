# 课业任务（悟禅）流程记录

## 环境与素材

- 真机取材：2026-07-07，`127.0.0.1:16416`，`1280x720`
- 原始 55 帧连续探针已清理，仅保留后续模板回归所需的代表帧
- 代表帧位于 `tests/fixtures/ymjh/kyrw_wuchan_20260707/`

## 已确认流程

1. 从活动「江湖」进入悟禅，再进入课业子面板。
2. 自动寻路到普照 NPC，兼容“悟禅”和“课业”动作按钮。
3. 确认课程并处理任务侧栏追踪、场景对话和自动寻路。
4. 物品不足时依次尝试商城、摆摊和全服摆摊获取。
5. 一键提交后，以课程完成提示和任务追踪消失作为完成依据。

## 保留的代表状态

- `01_activity_jianghu_wuchan_entry.webp`：活动入口
- `03_wuchan_detail_course_forward.webp`：课业子面板
- `09_npc_puzhao_wuchan_button.webp`：NPC 动作按钮
- `26_single_tap_wuchanchang_toast.webp`：已有课程提示
- `36_manual_accept_current_state.webp`：任务追踪状态
- `40_course_path_or_dialog.webp`：流程对话
- `46_stage_5_acquire_route_mall.webp`：获取途径
- `49_after_buy_18_humabing.webp`：购买后状态
- `51_course_complete_dialog.webp`：完成提示

## 回归重点

- 活动入口和 NPC 按钮必须使用模板确认，不能仅按固定坐标推断成功。
- 获取物品的多个路径允许失败回退，但必须有总超时。
- 完成验证以真实 UI 状态为准，不能因前往按钮暂时未识别而虚假成功。
