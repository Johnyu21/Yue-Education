# Dify 配置与正式项目测试账号使用说明

更新日期：2026-10-17。项目路径：C:/Users/Windows/PycharmProjects/Yue-Education。

这份说明按当前项目代码和六份DSL核对编写。照着完成“导入应用 → 配模型 → 发布 → 填URL和KEY → 重启后端 → 页面验证”即可逐个接入助手。

**已经完成的事项：**5174演示环境的14个账号及关联资料，已经按你的要求初始化到正式项目连接的 yue_education 数据库、public schema。没有覆盖已有账号或重置已有密码。文档第九节列出全部账号。

**目前还需要你填写的事项：**六个Dify应用的真实API Key、模型供应商配置和应用发布。此次没有启用真实Dify调用；当前正式配置仍为 DIFY_MODE=disabled、M5_AI_MODE=DISABLED。六份DSL需要在你的Dify实例导入并验证后才算真实可用。

## 一、URL和KEY到底填在哪个文件

打开下面这个文件：

~~~text
C:\Users\Windows\PycharmProjects\Yue-Education\backend\.env
~~~

在PyCharm左边展开 backend，找到 .env；它是以点开头的文件。

- **实际填写：backend/.env。**当前文件中尚未列出的URL或KEY项，可以按第三节补充。
- **格式参考：backend/.env.example。**它只是模板，改模板不会改变正在运行的项目配置。
- **读取代码：backend/app/core/config.py。**通常不用修改这个Python文件。
- **日报/报告读取规则：backend/app/services/m5_report_config.py。**它同样读取共享配置；当前代码不再加载独立的 .env.m5。
- **frontend/.env.local只用于前端代理/API地址。**Dify应用KEY应留在后端 .env 中。

填写时，每项一行，使用英文等号。已有的 DIFY_MODE、M5_AI_MODE 等行请直接修改原行，避免重复添加同名配置。保留现有数据库、JWT等配置。

Dify应用KEY通常以 app- 开头；它与DeepSeek等模型供应商的KEY不同。模型供应商KEY在Dify的模型供应商配置中填写，项目后端填写的是每个Dify应用自己的API Key。官方也要求应用KEY保留在后端。[Dify官方：获取应用API Key](https://docs.dify.ai/en/api-reference/guides/get-started)

## 二、所有Dify助手和KEY的对应表

当前共有**六个Workflow应用**。其中客户研判、报告生成通过页面按钮调用，其余通过对应对话窗口使用。

| 能力/应用 | 页面入口与用途 | 导入的DSL文件 | 在backend/.env填写的KEY |
| --- | --- | --- | --- |
| 访客咨询 WF_VISITOR | 访客页面“在线咨询”，回答公开项目/活动问题，收集咨询草稿 | dify/wf_entry.yml | DIFY_VISITOR_KEY |
| 客户研判 WF_ASSESSMENT | 客户管理中的研判、简历提取；负责提取事实与缺项 | dify/wf_profile.yml | DIFY_ASSESSMENT_KEY |
| 企业员工助手 WF_ENTERPRISE | 员工页面“员工助手”，查询待办、客户、申请等，生成待确认的办理建议 | dify/wf_enterprise.yml | DIFY_ENTERPRISE_KEY |
| 学生服务助手 WF_STUDENT | 学生登录后的“学生助手”，查询本人信息，整理申请或反馈草稿 | dify/wf_student.yml | DIFY_STUDENT_KEY |
| 日报收集助手 M5_报告助手 | 日报管理/报告中心的“报告助手”，多轮收集信息、补问、整理普通日报 | dify/m5_report_assistant.yml | M5_DIFY_ASSISTANT_KEY |
| 报告生成 M5_报告生成 | 报告中心“生成报告”按钮，按后端统计整理报告正文 | dify/m5_report_generation.yml | M5_DIFY_REPORT_KEY |

DIFY_REPORT_KEY 是报告生成的兼容配置项，**不是第七个应用**。M5报告优先使用 M5_DIFY_REPORT_KEY，未填写时按当前读取规则回退到 DIFY_REPORT_KEY。建议两项填写同一个“报告生成应用”的KEY。

“企业员工助手”和“日报收集助手”使用不同契约，分别填写各自应用的KEY。“日报收集”和“报告生成”也需要分别绑定对应应用。

六份DSL均位于：

~~~text
C:\Users\Windows\PycharmProjects\Yue-Education\dify\
~~~

## 三、可照抄的完整配置模板

**先在Dify中得到六个真实应用KEY，再替换下面的占位值。此段用于全部启用的情况。**

下面的地址沿用你之前提供的Dify地址；如果你的Dify控制台显示了其他域名或端口，请使用该实例实际的API地址。

~~~dotenv
# 前四类能力：访客、研判、企业员工、学生
DIFY_MODE=live
DIFY_BASE_URL=http://8.138.150.132/v1

DIFY_VISITOR_KEY=app-REPLACE_WITH_VISITOR_KEY
DIFY_ASSESSMENT_KEY=app-REPLACE_WITH_ASSESSMENT_KEY
DIFY_ENTERPRISE_KEY=app-REPLACE_WITH_ENTERPRISE_KEY
DIFY_STUDENT_KEY=app-REPLACE_WITH_STUDENT_KEY

# 报告生成兼容项：与下面M5_DIFY_REPORT_KEY填写同一个KEY
DIFY_REPORT_KEY=app-REPLACE_WITH_REPORT_GENERATION_KEY

# M5日报收集与报告生成
M5_AI_MODE=DIFY
M5_DIFY_BASE_URL=http://8.138.150.132/v1
M5_DIFY_ASSISTANT_KEY=app-REPLACE_WITH_DAILY_ASSISTANT_KEY
M5_DIFY_REPORT_KEY=app-REPLACE_WITH_REPORT_GENERATION_KEY
M5_AI_TIMEOUT=45
~~~

填写要点：

1. app-REPLACE_WITH_... 全部替换成对应应用生成的真实KEY；保留app-等KEY自身内容。
2. URL中不带中文分号、书名号或额外空格。例如正确值是 http://8.138.150.132/v1 。
3. URL填写API基础地址，后端会追加 /workflows/run。不要把控制台地址、发布后的网页地址或完整 /workflows/run 地址当作基础地址。
4. 当前代码兼容基础地址是否带 /v1；为了方便核对，建议统一按上面的 /v1 结尾格式填写。
5. 同一Dify实例的六个应用通常共用URL，KEY分别属于各自应用。如果M5单独部署，可只把 M5_DIFY_BASE_URL 改成另一个实例的API地址。
6. 保存 .env 后，需要重启后端，见第六节。

### 两个启用开关必须分别检查

| 配置项 | 真正调用Dify | 模拟模式 | 关闭 |
| --- | --- | --- | --- |
| DIFY_MODE | live | mock | disabled |
| M5_AI_MODE | DIFY | DEMO | DISABLED |

DIFY_MODE负责前四类能力；M5_AI_MODE负责日报和报告，显式填写时优先于共享开关。当前文件已有 M5_AI_MODE=DISABLED，所以**只把DIFY_MODE改成live，日报/报告仍不会调用Dify**。

### 如果暂时只接你自己的两个M5应用

可先采用以下组合，逐步完成其余成员应用：

~~~dotenv
DIFY_MODE=disabled
DIFY_BASE_URL=http://8.138.150.132/v1

M5_AI_MODE=DIFY
M5_DIFY_BASE_URL=http://8.138.150.132/v1
M5_DIFY_ASSISTANT_KEY=app-REPLACE_WITH_DAILY_ASSISTANT_KEY
M5_DIFY_REPORT_KEY=app-REPLACE_WITH_REPORT_GENERATION_KEY
DIFY_REPORT_KEY=app-REPLACE_WITH_REPORT_GENERATION_KEY
M5_AI_TIMEOUT=45
~~~

此组合下，你的日报助手和报告生成可调用Dify，其余四类AI仍显示未启用。它是上一份完整模板的另一种启用组合，选择一种并修改对应原行即可。

## 四、在Dify里如何得到六个KEY

按第二节的六份文件，分别完成下面步骤。

1. 打开Dify的工作室/Studio，选择导入DSL，选中对应 .yml 文件。
2. 确认应用类型为 **Workflow / 工作流**。当前后端使用 /workflows/run；不能用Chatflow或普通聊天应用的KEY替代。
3. 打开画布，检查LLM和问题分类器节点，为它们选择当前实例可用的模型。模型插件安装失败或模型未配置，需要先在Dify中处理完成。
4. 按下一节绑定需要的知识库。
5. 在Dify画布中试运行，检查开始变量和结束输出。
6. 点击发布/发布更新。更改画布后，再次发布才能让API使用新版本。
7. 进入该应用的API访问/访问API区域，创建或管理API Key，复制到 .env 的对应项，同时核对该处显示的API基础地址。
8. 记录KEY对应的应用，避免六个应用互相填错。

当前官方说明：工作流API执行的是已发布的Workflow；支持blocking和streaming两种返回方式。[Dify官方：运行工作流](https://docs.dify.ai/en/api-reference/workflow-runs/run-workflow) 发布更新的操作见[官方快速入门](https://docs.dify.ai/en/guides/application-orchestrate/creating-an-application)。

本项目六份DSL存在不同导出版本。出现导入或插件版本提示时，应按你的Dify实例核对并检查节点完整性，不能只凭文件成功导入就认定全部可运行。M5两份DSL包含DeepSeek插件引用；导入后仍需检查实际可用模型和供应商配置。

## 五、模型、知识库和输入输出怎么检查

### 1. 每份应用需要配置哪些节点

以下数量依据本次仓库中实际DSL读取：

| 应用 | 需检查的模型节点 | 知识库处理 |
| --- | --- | --- |
| WF_VISITOR | 1个LLM | 有1个知识检索节点，绑定公开资料库 |
| WF_ASSESSMENT | 1个LLM | 当前无知识检索节点，从传入材料提取字段 |
| WF_ENTERPRISE | 12个LLM、1个问题分类器 | 有1个知识检索节点，绑定员工资料库 |
| WF_STUDENT | 1个LLM | 当前导出无知识检索节点；后续添加学生FAQ检索时再绑定学生资料库 |
| M5_报告助手 | 1个LLM | 当前无知识检索节点，使用后端传入的草稿和历史消息 |
| M5_报告生成 | 1个LLM | 当前无知识检索节点，使用后端传入的指标与事实 |

含知识检索节点的应用，应选择实际可用的知识库并试运行。检索节点留空可能导致该节点报错；暂不使用检索时，需要在Dify画布中调整相应分支后重新发布。

公开库可放公司介绍、已确认的项目说明、公开政策说明与咨询FAQ；员工库可放服务流程、操作规范及内部FAQ。学生个人档案、投诉正文、心理观测及账号密码不作为这些通用知识库的文档导入。

### 2. 六份工作流统一的变量名称

~~~text
开始节点输入：payload_json
类型：段落/字符串，内容为JSON文本

结束节点输出：output_json
类型：JSON字符串，内容应是一个JSON对象
~~~

变量名大小写和拼写要一致。保留DSL中的解析、净化等代码节点；结束节点需要把正确的上游结果映射到 output_json。

各应用最终对象的大致要求如下，完整提示词与代码节点已在对应DSL中：

| 应用 | output_json内的主要内容 |
| --- | --- |
| 访客咨询 | answer、intent、draft、missing_fields、sources、warnings |
| 客户研判 | facts、evidence、missing_fields、warnings |
| 企业员工助手 | intent、params、draft、answer、missing_fields、sources、warnings |
| 学生助手 | intent、draft、answer、missing_fields、sources；按需返回observation |
| 日报收集 | answer、content；content包含work_summary、items、difficulties、next_plan |
| 报告生成 | narrative，即整理后的报告正文 |

前四类由后端以blocking调用；M5两类以streaming调用。M5必须等到工作流成功结束，且最终包含有效output_json；仅有LLM中间输出还不算完成。

### 3. 日报助手的画布试运行例子

把下面内容作为payload_json输入框中的文本：

~~~json
{
  "task": "DAILY_COLLECT",
  "content_policy": "日报仅记录普通工作，不包含心理原文或投诉明细",
  "message": "今天跟踪了3名学生的入学进度，困难：无",
  "draft": {
    "work_summary": "",
    "items": [],
    "difficulties": "",
    "next_plan": ""
  },
  "history": [],
  "selected_student_ids": [],
  "report_date": "2026-10-17"
}
~~~

检查最终output_json中是否有answer和content。后端负责保存多轮状态，工作流每次接收后端传来的历史与草稿。普通日报只记录普通工作；心理和投诉内容使用专项板块。

### 4. 报告生成应用的画布试运行例子

~~~json
{
  "task": "REPORT_GENERATE",
  "type": "DAILY_WEEK",
  "start_date": "2026-10-12",
  "end_date": "2026-10-17",
  "scope": "演示部门",
  "metrics": [{"label": "已通过日报", "value": 3, "unit": "篇"}],
  "facts": [{"section": "工作进展", "text": "本周完成了3篇已通过审核的普通日报。"}],
  "warnings": []
}
~~~

检查最终output_json是否包含非空narrative。模型只能整理传入事实，不能修改指标、编造收入、替用户保存报告或提交审核。网页保存继续使用后端预览快照。

### 5. 当前工作流的边界

当前六份DSL没有调用本系统写接口的HTTP节点。Dify负责理解、提取或生成建议；登录身份、数据范围、签名确认、保存与审核由本系统后端处理。

旧资料如果仍写着“把学生JWT传给Dify”“让Dify直接调用后端写接口”或设置backend_base_url，那属于历史设计。当前接入以本说明、实际六份DSL和后端代码为准。

## 六、填写后怎样让配置生效

在正在运行后端的终端按Ctrl+C停止，然后在PowerShell执行：

~~~powershell
cd C:\Users\Windows\PycharmProjects\Yue-Education\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
~~~

如果通过PyCharm运行，也可以停止后重新运行同一个后端启动配置。检查运行配置中的环境变量：进程环境中的同名配置会覆盖 .env，尤其注意旧的 DIFY_MODE、M5_AI_MODE。

后端读取配置后会缓存，因此保存文件后仅刷新浏览器通常不足以生效；需要重启后端。前端已经通过本项目后端转发AI请求，不需要在浏览器输入Dify KEY。

本地前端尚未启动时，在另一个终端执行：

~~~powershell
cd C:\Users\Windows\PycharmProjects\Yue-Education\frontend
npm run dev
~~~

打开正式项目：http://127.0.0.1:5173/#/login 。

## 七、六类能力如何在页面逐个验证

| 要验证的能力 | 登录/进入位置 | 建议测试内容 | 成功时应看到什么 |
| --- | --- | --- | --- |
| 访客咨询 | 正式项目访客首页，点击在线咨询 | 了解公开留学项目 | 返回对应问答或补充资料提示，不凭空生成合作院校 |
| 客户研判 | ui_advisor登录，客户管理，选择本人客户，发起研判/简历提取 | 使用已核实的客户资料 | 返回提取事实、依据和缺项；录取判定仍以审核规则为准 |
| 企业员工助手 | ui_advisor登录，点击员工助手 | 查询我的待办事项 | 返回本人授权范围数据；办理建议需本人再次确认 |
| 学生助手 | 13911110001登录，点击学生助手 | 查询我的成绩 | 返回本人已登记成绩；其他学生资料不应出现 |
| 日报收集 | ui_advisor登录，日报管理，点击报告助手 | 今天跟踪了3名学生的入学进度 | 收集工作草稿、缺项时追问，核对后由员工保存提交 |
| 报告生成 | ui_head登录，报告中心，选择报告和日期，点击生成报告 | 先完成员工日报提交和主管审核，再汇总 | 后端提供真实指标，Dify整理正文；保存后可导出 |

新初始化账号还没有已审核日报，第一次日报汇总可能为空。可先用ui_advisor填写日报提交，再用ui_head审核通过，然后生成日报日/周汇总。主管只写主管周报，不填写普通员工日报。

新增学生均标记为演示资料，专项心理报告按既有后端规则排除演示学生；没有心理观测或投诉记录时，相应报告也可能没有明细。不能把空统计解释为Dify未接通。

判断真实AI是否接通时，请同时核对网页AI状态和Dify运行记录。后端接口HTTP 200只表示本次请求被处理；AI不可用时也可能返回保留的事实文本。LIVE表示真实调用来源，MOCK表示模拟，UNAVAILABLE表示本次未得到可用模型结果；DETERMINISTIC表示后端规则/查询直接给出结果。

## 八、常见问题对照

| 现象 | 优先检查 |
| --- | --- |
| KEY已填，仍提示AI未启用 | DIFY_MODE是否为live；M5_AI_MODE是否仍为DISABLED；是否重启了后端 |
| 员工助手正常，日报助手不正常 | 检查M5_AI_MODE、M5_DIFY_BASE_URL、M5_DIFY_ASSISTANT_KEY |
| 日报助手正常，生成报告失败 | 检查M5_DIFY_REPORT_KEY是否属于“报告生成”应用；最终是否返回narrative |
| Dify返回401/403 | KEY是否正确、是否属于该应用、是否误用了模型供应商KEY或其他Dify实例KEY |
| Dify返回404 | URL/端口是否正确；应用类型是否为Workflow；基础地址是否误填了页面路径 |
| 缺少payload_json | 开始节点变量名称是否与请求一致 |
| 没有output_json或格式不合法 | 检查结束映射、解析/净化代码节点和最终JSON，不要只检查模型的中间文字 |
| Studio里可以跑，项目仍使用旧流程 | 是否发布了最新修改，项目KEY是否指向正确应用 |
| 知识库节点报错 | 访客/企业工作流的检索节点是否绑定了实际资料库 |
| 模型节点报错或插件安装失败 | 在Dify端先解决模型供应商、插件环境和网络问题；项目填KEY不会修复插件依赖 |
| 超时或429 | 检查供应商状态及Dify运行日志；M5超时可在M5_AI_TIMEOUT中按实际需要调整 |
| 5174怎么改KEY都没变化 | 5174连接独立演示后端，启动时固定使用mock/禁用AI；真实Dify联调请用5173正式项目 |
| 刚重置密码后旧登录失效 | 属于正常行为；使用新临时密码登录，按提示改密 |

ASR语音转写是单独供应商配置（ASR_ENABLED、ASR_BASE_URL、ASR_API_KEY、ASR_MODEL），不计入上面六个Dify应用；只填Dify KEY不会自动启用语音转写。

## 九、已初始化到正式项目的测试账号

**正式项目登录地址：http://127.0.0.1:5173/#/login**

**本次新建账号的统一初始密码：FrontQA-2026!**

| 身份 | 登录账号 | 姓名/用途 |
| --- | --- | --- |
| 系统管理员 | ui_admin | 联调管理员，系统账号与密码管理 |
| 部门主管 | ui_head | 联调主管，本部门审核与周报 |
| 顾问一 | ui_advisor | 联调顾问，负责4名学生 |
| 顾问二 | ui_advisor2 | 林顾问（演示），负责3名学生 |
| 班主任一 | ui_teacher | 联调班主任，负责4名学生 |
| 班主任二 | ui_teacher2 | 陈老师（演示），负责3名学生 |
| 入职员工 | ui_first | 首次联调员工，首次登录需要修改密码 |
| 学生一 | 13911110001 | 联调学生 |
| 学生二 | 13911110002 | 王梓涵（演示） |
| 学生三 | 13911110003 | 赵沐晴（演示） |
| 学生四 | 13911110004 | 刘星宇（演示） |
| 学生五 | 13911110005 | 周思远（演示） |
| 学生六 | 13911110006 | 黄雨桐（演示） |
| 学生七 | 13911110007 | 何嘉宁（演示） |

账号、姓名、成绩、联系方式与项目资料用于课程测试，均为合成资料。本次密码只适用于这些新建测试账号，原来已有的管理员/组员账号密码保持不变；后续主动改密后以新密码为准。

已建立部门、2个班级、2个项目、7名学生与顾问/班主任关系，并初始化对应客户、项目关联、成绩、日程、通知及1个活动。班主任身份来自班级关联，部门主管身份来自部门主管关系，数据库基础employee_role仍可能是ADVISOR。

正式项目5173与独立演示5174现在拥有相同的这批初始账号，但分别连接不同数据库环境。之后在一边改密码、写日报或修改学生资料，不会自动同步到另一边。

本次验证：14个账号的初始密码均已核对；管理员、主管、顾问、班主任和学生已通过正式后端API登录。初始化脚本的完整性、重复执行保留密码、同名冲突不覆盖等2项测试已在独立测试库通过。

## 十、以后换数据库或重新初始化时怎么做

使用此次新增的专用脚本：

~~~text
backend/scripts/seed_m5_frontend_demo.py
~~~

它读取当前 backend/.env 对应数据库。**默认只检查，不写数据：**

~~~powershell
cd C:\Users\Windows\PycharmProjects\Yue-Education\backend
.\.venv\Scripts\python.exe -m scripts.seed_m5_frontend_demo
~~~

结果含READY_TO_INSERT表示无冲突，可以新增；ALREADY_INITIALIZED表示资料已经存在；CONFLICT表示有同名账号、编码、手机号或归属冲突，需要先核对，不会自动覆盖。

明确初始化当前正式开发库时执行：

~~~powershell
.\.venv\Scripts\python.exe -m scripts.seed_m5_frontend_demo --apply --database yue_education
~~~

--database必须与当前配置库名完全一致。脚本仅用于dev/test环境，一次事务新增全部资料；异常时整体回滚。重复执行不会重置已改过的密码，也不会恢复初始状态。执行记录写入backend/logs/frontend-demo-init-*.json，不记录数据库密码或Dify KEY。

当前正式库已经初始化完成，无需为了登录再次执行。已有表结构与其他成员的业务代码未因本次初始化而改动。

## 十一、配置完成后的核对清单

- [ ] 六个Dify应用都已导入，类型均为Workflow。
- [ ] 模型可用，访客/企业需要的知识检索节点已正确绑定。
- [ ] 每个应用都已发布，payload_json和output_json拼写正确。
- [ ] backend/.env的六类KEY分别对应正确应用，报告兼容KEY也已核对。
- [ ] DIFY_MODE、M5_AI_MODE设置符合当前要启用的范围。
- [ ] 已重启后端，使用5173按第七节逐类验证。
- [ ] Dify运行日志显示对应应用真实成功，页面状态和事实来源一致。

## 十二、参考依据

项目实际读取和调用代码：

- [共享配置](../backend/app/core/config.py)
- [M5配置及优先级](../backend/app/services/m5_report_config.py)
- [通用Dify调用入口](../backend/app/integrations/dify/__init__.py)
- [M5工作流/SSE处理](../backend/app/integrations/dify/m5_report_ai.py)
- [已有业务契约说明](Dify业务契约与联调说明.md)

官方参考：[API入门与应用KEY](https://docs.dify.ai/en/api-reference/guides/get-started)、[运行Workflow](https://docs.dify.ai/en/api-reference/workflow-runs/run-workflow)、[Workflow API说明](https://docs.dify.ai/en/api-reference/guides/workflow)。
