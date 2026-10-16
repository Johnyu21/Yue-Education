"""
Dify 适配器（规范要求 integrations/dify/）

作用：后端调 Dify 的**唯一出口**。
⚠️ 前端不直连 Dify —— key 只在后端。

职责：
  - 选择工作流（访客/研判/员工/学生/报告）
  - 组装 payload
  - 超时控制（读取预算 45 秒）
  - 校验返回结构（不符合约定 → AIBadResponseError）
  - 失败降级（AI 不可用时业务仍可继续）

⚠️ 调用约定（规范 02 文档）：
  每个 Workflow 开始节点用字符串变量 payload_json，
  结束节点用 output_json，取 data.outputs.output_json 后解析一次 JSON。
"""
