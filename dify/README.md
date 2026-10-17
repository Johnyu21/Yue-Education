# Dify 工作流


> 六个 Workflow 的设计与导出文件（DSL）
> ⚠️ API key 不写在本目录（进后端 `.env`）

## 工作流与文件对应

| 工作流 | 用途 | 谁用 | DSL 文件 | 后端 key |
|---|---|---|---|---|
| `WF_VISITOR` | 访客咨询（公开问答/留资草稿/活动意向） | 公开门户 | `wf_entry.yml` | `DIFY_VISITOR_KEY` |
| `WF_ASSESSMENT` | 客户研判（字段提取/证据/缺项，不做判定） | 员工（研判面板） | `wf_profile.yml` | `DIFY_ASSESSMENT_KEY` |
| `WF_ENTERPRISE` | 受控意图（员工助手） | 员工助手 | `wf_enterprise.yml` | `DIFY_ENTERPRISE_KEY` |
| `WF_STUDENT` | 受控意图（学生助手） | 学生助手 | `wf_student.yml` | `DIFY_STUDENT_KEY` |
| `REPORT_ASSISTANT` | 日报草稿收集 | 员工日报 | `m5_report_assistant.yml` | `M5_DIFY_ASSISTANT_KEY` |
| `REPORT_GENERATION` | 报告正文生成（数字仍由后端算） | 管理层 | `m5_report_generation.yml` | `M5_DIFY_REPORT_KEY` |

> 注：设计文档早期把访客/研判写作 `WF_ENTRY`/`WF_PROFILE`，代码与配置键统一为
> `WF_VISITOR`/`WF_ASSESSMENT`（对应 `DIFY_VISITOR_KEY`/`DIFY_ASSESSMENT_KEY`）；
> 文件名沿用旧名 `wf_entry.yml`/`wf_profile.yml`。
> `DIFY_REPORT_KEY` 为兼容保留，M5 报告优先读 `M5_DIFY_REPORT_KEY`。

## 目录约定

```
dify/
├── wf_entry.yml                 # WF_VISITOR  访客客服（DSL 0.1.4）      —— M2
├── wf_profile.yml               # WF_ASSESSMENT 客户研判（DSL 0.1.4）    —— M2
├── wf_enterprise.yml            # WF_ENTERPRISE 员工助手（DSL 0.1.3）    —— M3
├── wf_student.yml               # WF_STUDENT 学生助手（DSL 0.1.3）       —— M4
├── m5_report_assistant.yml      # REPORT_ASSISTANT 日报收集（DSL 0.5.0） —— M5
├── m5_report_generation.yml     # REPORT_GENERATION 报告生成（DSL 0.5.0）—— M5
├── Dify创建配置说明.md           # 导入、模型与知识库绑定步骤
├── variables.md                 # 输入输出变量说明（四个助手契约）
└── eval_samples.md              # 评测样本（30 条起步）
```

## ⚠️ 注意

- **DSL 导出不含 API key** —— key 只放后端 `.env`
- **导入后要重新绑定知识库和模型**（DSL 里是占位），并确认两个代码节点没被删掉：
  `WF_VISITOR` / `WF_ASSESSMENT` 依赖"解析入参 + 输出净化"，缺了会把模型的解释文字当成 JSON
  导致 `AI_BAD_RESPONSE`
- **DSL 版本不一致是历史原因**：M2 两份为 `0.1.4`、M3/M4 为 `0.1.3`、M5 两份为 `0.5.0`；
  同一实例导入时提示"版本差异"属正常警告，但请按实际实例重新导出核对一次
- **三个知识库按受众隔离**：`public`（访客）/ `employee`（员工）/ `student`（学生）；
  客户库明细、投诉正文、心理观测**不进任何知识库**
- **AI 调用走后端适配器** `app/integrations/dify/`，不由前端直连
- **mock 优先**：后端 `DIFY_MODE=mock` 时使用 `mock_samples.py` 的离线样本，
  不依赖 Dify 即可跑通全链路；接上 key 后改为 `DIFY_MODE=live` 即切换真实调用。
  `DIFY_MODE=disabled` 时直接降级（`aiStatus=UNAVAILABLE`），不发网络请求
