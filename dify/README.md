# Dify 工作流

> 五个 Workflow 的设计与导出文件（DSL）
> ⚠️ API key 不写在本目录（进后端 `.env`）

## 五个工作流

| 工作流 | 用途 | 谁用 | 后端 key |
|---|---|---|---|
| `WF_ENTRY` | 访客咨询 | 公开门户 | `DIFY_VISITOR_KEY` |
| `WF_PROFILE` | 客户研判 | 员工（研判面板） | `DIFY_ASSESSMENT_KEY` |
| `WF_COMMAND` | 受控意图 | 员工/学生助手 | `DIFY_ENTERPRISE_KEY` / `DIFY_STUDENT_KEY` |
| `WF_REPORT` | 报告分析 | 管理层 | `DIFY_REPORT_KEY` |

## 目录约定

```
dify/
├── wf_entry.yml          # 导出的 DSL（不含 key）
├── wf_profile.yml
├── wf_command.yml
├── wf_report.yml
├── variables.md          # 输入输出变量说明
└── eval_samples.md       # 评测样本（30 条起步）
```

## ⚠️ 注意

- **DSL 导出不含 API key** —— key 只放后端 `.env`
- **导入后要重新绑定知识库和模型**（DSL 里是占位）
- **AI 调用走后端适配器** `app/integrations/dify/`，不由前端直连
