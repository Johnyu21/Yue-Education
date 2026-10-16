# Dify 工作流

> 五个 Workflow 的设计与导出文件（DSL）
> ⚠️ API key 不写在本目录（进后端 `.env`）

## 五个工作流

| 工作流 | 用途 | 谁用 | 后端 key |
|---|---|---|---|
| `WF_VISITOR` | 访客咨询（公开问答/留资草稿/活动意向） | 公开门户 | `DIFY_VISITOR_KEY` |
| `WF_ASSESSMENT` | 客户研判（字段提取/证据/缺项，不做判定） | 员工（研判面板） | `DIFY_ASSESSMENT_KEY` |
| `WF_ENTERPRISE` | 受控意图（员工助手） | 员工助手 | `DIFY_ENTERPRISE_KEY` |
| `WF_STUDENT` | 受控意图（学生助手） | 学生助手 | `DIFY_STUDENT_KEY` |
| `WF_REPORT` | 报告分析 | 管理层 | `DIFY_REPORT_KEY` |

> 注：设计文档早期把访客/研判写作 `WF_ENTRY`/`WF_PROFILE`，代码与配置键统一为
> `WF_VISITOR`/`WF_ASSESSMENT`（对应 `DIFY_VISITOR_KEY`/`DIFY_ASSESSMENT_KEY`）。

## 目录约定

```
dify/
├── wf_entry.yml          # WF_VISITOR  导出的 DSL（不含 key）—— M2
├── wf_profile.yml        # WF_ASSESSMENT 导出的 DSL          —— M2
├── wf_student.yml        # WF_STUDENT  导出的 DSL            —— M4
├── wf_command.yml        # WF_ENTERPRISE 导出的 DSL（待 M3 提供）
├── wf_report.yml         # WF_REPORT  导出的 DSL（待 M5 提供）
├── variables.md          # 输入输出变量说明（WF_STUDENT / WF_VISITOR / WF_ASSESSMENT）
└── eval_samples.md       # 评测样本（30 条起步）
```

## ⚠️ 注意

- **DSL 导出不含 API key** —— key 只放后端 `.env`
- **导入后要重新绑定知识库和模型**（DSL 里是占位）
- **三个知识库按受众隔离**：`public`（访客）/ `employee`（员工）/ `student`（学生）；
  客户库明细、投诉正文、心理观测**不进任何知识库**
- **AI 调用走后端适配器** `app/integrations/dify/`，不由前端直连
- **mock 优先**：后端 `DIFY_MODE=mock` 时使用 `mock_samples.py` 的离线样本，
  不依赖 Dify 即可跑通全链路；接上 key 后改为 `DIFY_MODE=live` 即切换真实调用
