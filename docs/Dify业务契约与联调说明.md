# Dify业务契约与联调说明

当前状态：仓库内 DSL 已补齐"解析入参 + 输出净化"代码节点，输入输出契约与后端适配器对齐；
但**仍未在真实 Dify 实例验证**导入、模型与知识库绑定。M2 两份 DSL 只做到本地校验
（YAML 结构 + 代码节点行为），不能据此认定 AI 验收通过。

## 配置与六类能力

统一从 backend/.env 和进程环境读取；旧 .env.m5 不再作为第二套秘密来源。DIFY_MODE支持disabled/mock/live，生产禁止mock。M5_AI_MODE兼容DISABLED/DEMO/DIFY，其中DEMO输出标为MOCK且禁止生产使用。

| 能力 | 配置键 | 后端职责 | 工作流允许输出 |
|---|---|---|---|
| 访客咨询 | DIFY_VISITOR_KEY | 公开项目/活动筛选、会话草稿、确认卡 | answer/intent/draft/missing_fields/sources |
| 客户研判提取 | DIFY_ASSESSMENT_KEY | 授权、事实/规则快照、确定性判定与评分、条件回写 | facts/evidence/missing_fields/warnings |
| 企业助手 | DIFY_ENTERPRISE_KEY | 授权查询、对象消歧、写提议、确认签名 | intent/params/draft/answer/sources/warnings |
| 学生助手 | DIFY_STUDENT_KEY | 本人查询、服务/反馈/升学提议、同意检查 | intent/draft/answer/observation/missing_fields/sources |
| 日报收集助手 | M5_DIFY_ASSISTANT_KEY | 普通日报草稿、用户确认、提交审核 | answer/content，内容符合DailyContent |
| 报告生成 | DIFY_REPORT_KEY或M5_DIFY_REPORT_KEY | 指标与事实由后端计算，生成快照 | narrative，不能改写指标或执行保存 |

日报助手使用专用应用key；不能把企业助手的key直接代入，因为两者输出契约不同。DIFY_BASE_URL默认共用，M5_DIFY_BASE_URL可覆盖。key只在后端配置，不进入前端、DSL或日志。

## 通用 HTTP 契约

普通工作流：POST {base}/v1/workflows/run，若base已包含/v1不会重复拼接。Authorization为后端管理的Bearer key，inputs.payload_json是JSON字符串，response_mode=blocking。响应从data.outputs.output_json取对象或解析字符串JSON。错误状态、非对象和非JSON明确返回AI错误，401/403/429/5xx/超时都不会当成成功。

~~~json
{
  "inputs": {"payload_json": "{\"schema_version\":\"1.0\",\"message\":\"合成测试问题\"}"},
  "response_mode": "blocking",
  "user": "opaque-backend-user-id"
}
~~~

~~~json
{
  "data": {
    "status": "succeeded",
    "outputs": {"output_json": "{\"schema_version\":\"1.0\",\"intent\":\"OTHER\",\"answer\":\"请补充信息\"}"}
  }
}
~~~

M5日报和报告使用streaming，由后端消费SSE并仅接受workflow_finished且succeeded的最终输出。流中断、节点异常、格式错误均降级为UNAVAILABLE；不把失败模型片段包装成成功。

输出是提取或建议，不是授权。工作流不得接收登录JWT，不得用HTTP节点调用本系统写接口，不得自行声明confirmed=true、生成业务request_key或更新version。wf_student.yml已移除原来的直接业务写HTTP路径；真实发布前仍须在Dify中核对模型和节点配置。

## 学生助手示例

~~~json
{
  "schema_version": "1.0",
  "intent": "SERVICE_DRAFT",
  "answer": "已整理考务申请，请核对后提交",
  "draft": {"service_type":"EXAM","title":"考试安排咨询","description":"合成测试描述"},
  "missing_fields": [],
  "sources": [],
  "warnings": []
}
~~~

后端校验draft，签发SUBMIT_SERVICE的proposal，包含requestKey/confirmationToken/preview。此时student_admin_service仍未写入。用户确认后，前端调用普通提交接口；后端重新鉴权、比对确认内容与request_key、执行幂等和事务。

学生观测observation仅在当前有效心理同意下处理；直接风险词规则可先于Dify完成，不能因模型超时吞掉真实关怀事件。模型情绪标签不作为诊断，也不回显内部标签给学生。

## 研判约束

Dify提取的事实只作为参考证据，不直接并入正式事实。准入判定来自已审核的admission_rules，支持all_of/any_of组合；缺失或非法规则返回NEEDS_INFO，不给虚假MATCH。研判调用前结束数据库事务；回写检查任务号、起始版本、项目规则版本和当前权限，事实或规则变化时旧结果作废。

缺失项口径由后端在 payload 里给出的 required_fields 决定：**学历 education 无条件必填**，
其余字段（语言成绩、出生日期、城市等）只有被已审核规则引用时才必填；工作流的 missing_fields
只能是它的子集。模型输出的 score/decision 在净化节点被直接丢弃。
project_rules[].rules 在规则未审核时为 null，工作流不得据此推断门槛。
访客侧 payload 另含 draft（已收集草稿）与 history（最近 8 条问答），用于多轮续填与指代消解，
两者都只含公开对话内容，不含客户库或员工数据。

## 报告与日报约束

报告生成payload包含已校验的type、日期范围、scope、metrics、facts、warnings。模型只润色narrative；保存继续绑定预览snapshot_id，不能再次调用模型覆盖事实。

日报payload的content_policy要求普通工作，不收集心理原文、投诉内容或专项事件引用；后端同样拒绝这些结构化条目。AI关闭时可人工填写；未知内容返回缺字段或不可用，不用演示文案冒充真实生成。

## 真正联调时逐项验证

1. 分别创建六个应用或提供六个明确兼容的应用契约，配置对应key、模型和经过审核的知识库；先使用合成资料。
2. 校验Start/End变量、字符串JSON、schema_version、空值、非法intent与缺字段返回。
3. 模拟超时、鉴权失败、429、非JSON、错误schema和SSE中断，确认页面保留表单与现有草稿。
4. 确认模型不能跨用户读取、不能直接执行写接口，确认卡改内容/换人/换key/换对象/换版本都被拒绝。
5. 确认研判不把未经核对的提取当成事实，报告不重算历史指标，撤权或撤回同意立即阻断敏感读取和导出。
6. 留存真实运行ID、时间、应用版本和合成验收结果，再把该能力从“契约已准备”标记为“真实集成通过”。

ASR使用可配置的兼容转写接口，ASR_BASE_URL应包含供应商API前缀，后端追加/audio/transcriptions。未配置时503；有text时也仅返回待核对草稿。未提供真实供应商，本轮没有真实语音识别验收结果。
