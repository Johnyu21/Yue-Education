# Dify 工作流

目标 Dify **1.12.1 / DSL 0.5.0**，保留工作室当前 **deepseek-v4-flash**。工作流无 HTTP、数据库和工具节点；后端执行查询与确认后的写操作。

知识库已在工作室配置。团队只需在知识检索节点选库并发布，再提供应用 API Key 与服务地址；不用填写知识库 UUID 或运行生成脚本。

| 应用 | YML | 后端配置 |
| --- | --- | --- |
| 客服助手 | wf_entry.yml | DIFY_VISITOR_KEY |
| 学生助手 | wf_student.yml | DIFY_STUDENT_KEY |
| 企业助手 | wf_enterprise.yml | DIFY_ENTERPRISE_KEY |
| 客户研判 | wf_profile.yml | DIFY_ASSESSMENT_KEY |
| 报告助手 | m5_report_assistant.yml | M5_DIFY_ASSISTANT_KEY |
| 报告生成 | m5_report_generation.yml | M5_DIFY_REPORT_KEY |

统一输入 payload_json，统一输出 output_json，均为JSON字符串。密钥只放被忽略的 backend/.env，模型凭据只放 Dify 工作室。

2026-10-18 真实冒烟11/11、六类报告最终逐项复测均LIVE。实际覆盖范围、测试记录和正式业务规则待确认项见[工作流与联调说明](../docs/Dify1.12.1工作流优化与知识库接入说明.md)。

- [工作室导入配置](Dify创建配置说明.md)
- [变量与业务契约](variables.md)
- [验收用例](eval_samples.md)

开发生成入口 tools/build_dify_workflows.py 会保留当前YML里的模型和知识库绑定。workflow_config.json不管理知识库UUID或启用开关。
