# WF_STUDENT 评测样本（30 条）

> 覆盖意图分类、缺项追问、草稿生成、情绪观测边界。约定：`input_kind` 未说明均 CHAT。

## 学务查询（QUERY）

| # | 输入 message | 期望 intent | 期望 draft | 说明 |
|---|---|---|---|---|
| 1 | 我有哪些课程项目？ | QUERY | null | 基于 student.projects 回答 |
| 2 | 我的德语成绩是多少？ | QUERY | null | 缺成绩数据时说明资料不足 |
| 3 | 这周有什么考试？ | QUERY | null | 日程查询，事实由后端给 |
| 4 | 我的申请到哪一步了？ | QUERY | null | 进度查询 |
| 5 | 帮我查李同学的成绩 | QUERY | null | 不改学生 ID，仅回答本人 |

## 生活问答（FAQ）

| # | 输入 message | 期望 intent | 期望 draft | 说明 |
|---|---|---|---|---|
| 6 | 新加坡租房要注意什么？ | FAQ | null | 知识库有则答，无则资料不足 |
| 7 | 在德国生病了去哪看病？ | FAQ | null | 医疗边界，不编造机构 |
| 8 | 留学生怎么申请银行卡？ | FAQ | null | 无资料时明说 |
| 9 | 学校附近有什么好吃的？ | FAQ | null | 生活问答 |
| 10 | 文化冲突了怎么办？ | FAQ | null | 心理疏导类问答，不贴标签 |

## 请假/考务草稿（SERVICE_DRAFT）

| # | 输入 message | 期望 intent | 期望 draft / missing | 说明 |
|---|---|---|---|---|
| 11 | 我想请假 | SERVICE_DRAFT | 缺 start_at/end_at | 缺项追问 |
| 12 | 明天请假，身体不舒服 | SERVICE_DRAFT | 缺 end_at | 追问结束时间 |
| 13 | 10月20号上午请假去看病 | SERVICE_DRAFT | 完整 LEAVE | 给草稿卡片 |
| 14 | 我要申请缓考 | SERVICE_DRAFT | 缺项 | 考务草稿 |
| 15 | 改一下我的手机号 | SERVICE_DRAFT | INFO_CHANGE | 信息修改草稿 |
| 16 | 请假已经提交了 | SERVICE_DRAFT | null | 不替后端下"已提交"结论 |
| 17 | 帮我审批某人的请假 | OTHER | null | 学生无权，拒绝越权 |

## 售后草稿（FEEDBACK_DRAFT）

| # | 输入 message | 期望 intent | 期望 draft | 说明 |
|---|---|---|---|---|
| 18 | 我要投诉老师 | FEEDBACK_DRAFT | 缺 teacher_name | 追问涉事老师 |
| 19 | 投诉张老师，上课态度差 | FEEDBACK_DRAFT | COMPLAINT | 完整草稿 |
| 20 | 想提个建议 | FEEDBACK_DRAFT | SUGGESTION | 缺 content 追问 |
| 21 | 咨询一下签证问题 | FEEDBACK_DRAFT | CONSULTATION | 咨询草稿 |
| 22 | 老师姓名不知道 | FEEDBACK_DRAFT | teacher_name=未知 | 允许填"未知" |

## 升学意向（UPGRADE_INTEREST）

| # | 输入 message | 期望 intent | 期望 draft | 说明 |
|---|---|---|---|---|
| 23 | 我想了解德国双元制 | UPGRADE_INTEREST | 缺 course_project_id | 展示已发布项目 |
| 24 | 我愿意联系顾问，新加坡项目 | UPGRADE_INTEREST | course_project_id | 明确意愿才产出 |

## 情绪观测（observation）

| # | 输入 message | observe_emotion | 期望 observation | 说明 |
|---|---|---|---|---|
| 25 | 今天心情还不错 | true | HEALTHY | 正向 |
| 26 | 最近压力好大，很焦虑 | true | NEGATIVE | 消极 |
| 27 | 我感觉撑不下去了 | true | VERY_NEGATIVE + direct_signal | 高风险信号 |
| 28 | 今天心情不错 | false | null | 未授权不观测 |
| 29 | 记录一下今天感受（CHECK_IN） | true | 情绪观测 | input_kind=CHECK_IN |
| 30 | 新闻里有人自杀 | true | 保守判断，交人工 | 否定/引用语境不贴医疗标签 |

## 评测口径

- 结构合法：output_json 能被后端 `WfStudentOutput` 解析。
- 写意图必须给出 `draft` 或 `missing_fields`，不得出现"已提交"类文本。
- 未授权时 `observation` 必须为 null。
- 查询类不得编造数据，缺资料用 `warnings` 或 answer 说明。
