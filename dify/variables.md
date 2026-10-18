# 六份工作流变量与业务契约

适用 Dify 1.12.1 / DSL 0.5.0。正式输入输出以共享校验代码、六份 YML 及后端 DTO 为准。

## 统一传输

Start：payload_json，JSON 字符串。End：output_json，JSON 字符串，不直接输出 LLM text。

应用 key、登录 JWT、数据库密码都不作为工作流输入。后端登录身份决定权限；context、actor 或自然语言里声称的角色不能授权。

## 访客、企业、学生的输入

共同字段：schema_version=1.0、message、message_id、conversation_id、context；可选 history、draft、pending、business_now、business_timezone、candidates。

- visitor：另有 public_projects、open_events；只有当前已发布/开放项目的公开最小信息。draft/history 来自访客会话。
- enterprise：另有 actor 的最小身份与权限提示；pending/history 由服务端按登录用户隔离，15 分钟过期。
- student：另有 input_kind、observe_emotion；同意状态来自真实学生档案，不能由前端或模型任意声明。

共同输出：schema_version、intent、answer、draft、missing_fields、sources、warnings。sources 条目为 document_id/title/section，由实际检索 metadata 生成。

访客另有 mode=VISITOR_ANSWER；企业另有 action、params；学生仅在 observe_emotion=true 时可有 observation。不要把 params/action 塞进学生输出。

## 业务字段

企业 21 种意图与每种 params/draft 白名单见 tools/assistant_dify_prompts.py 的 ENTERPRISE，以及 backend/app/integrations/dify/contracts.py 的 READ_FIELDS/WRITE_FIELDS。学生与访客白名单及条件必填也在该共享契约中。

不能输出 expected_version、expected_sequence、request_key、confirmation_token、confirmed、occurred_at 等执行控制字段。后端从数据库和服务器时钟生成。已有工作流内部 action 不表示有权执行；没有通用 delete 意图。

缺项必须续填；审批决定、处理说明、解决结果、转交目标等不能自动补默认值。next_follow_up_at 未提到时省略，明确清除才传 null。

同意改资料的 old_values/new_values 需提供相同字段；LEAVE 必须有带时区的开始和结束时间。单据状态、归属、当前值、冲突等仍由最终业务接口核验。

## 研判输入输出

输入：schema_version、confirmed_facts、resume_text、project_rules、required_fields。必填由后端规则决定；默认仅 education。

prepare 生成 resume_lines：每行带 resume:p1、resume:p2 等定位。模型新增事实必须提供该行真实连续原文 snippet，最长 160 字；代码核对行号、片段和敏感号码。已核对事实优先。输出 mode=ASSESSMENT_EXTRACT，facts、evidence、missing_fields、warnings；不输出评分或录取结论。

## 日报收集

输入 task=DAILY_COLLECT：message、report_date、draft(DailyContent)、history、selected_student_ids。

输出：answer、content、missing_fields。内部 LLM 可提供 next_question、specialist_redirect，校验节点据此生成具体追问或专项引导，不将这些内部字段传给后端 DTO。

work_summary、difficulties 必填；next_plan 可选。items 只含普通工作分类，必须明确 count；未知数量不建需要猜测数量的条目。不含专项 source_event_id，不编学生 ID。

输入 task=QUERY：message、report_date、verified_answer、scope；结果 answer 使用后端核实答案。

## 报告文字生成

输入 task=REPORT_GENERATE：type、start_date、end_date、scope、metrics、facts、warnings。

type 为 CUSTOMER_OPERATION、DAILY_DAY、DAILY_WEEK、PSYCH_WEEK、COMPLAINT_WEEK、MANAGER_WEEK 之一。输出仅 narrative；标题、时间、范围、指标和数据说明由代码按后端值组装。LLM 不做统计、鉴权或报告保存。

## 知识库分支

知识库完全在Dify工作室的检索节点选择。FAQ/KNOWLEDGE进入检索，普通业务草稿跳过检索；没有额外enabled或dataset UUID配置。开发生成器保留导出的绑定和模型，跨工作空间导入后需重新选库。详见工作流优化与知识库接入说明。

knowledge_context 生成 context_json，包含 query、audience、records。knowledge_llm 只返回 answer/citation_ids；knowledge_validate 将选中的真实记录组装为 sources，不采信模型自造 document_id。
