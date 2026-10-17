# WF_ENTERPRISE 企业助手 · Dify 创建/导入配置说明

> 对应文件：`dify/wf_enterprise.yml`
> 适用：Dify 1.12.x（Workflow 应用）
> 目标：导入后可运行；模型与知识库由使用者在 Dify 网页配置

---

## 1. 前置检查

| 项 | 要求 |
|---|---|
| Dify 版本 | 1.12.x（导入时提示 DSL 版本差异属正常警告） |
| 模型供应商 | 已配置至少一个可用模型（如 `langgenius/deepseek/deepseek`） |
| 网络 | Dify 能正常访问模型供应商；后端能出站访问 Dify |
| 账号 | 具备创建应用、创建知识库的权限 |

---

## 2. 导入工作流

1. 打开 Dify 控制台 → **工作室 / Studio** → **创建应用**
2. 选择 **导入 DSL 文件**（Import DSL）
3. 选择 `dify/wf_enterprise.yml`
4. 确认导入，应用名应为 `WF_ENTERPRISE`
5. 打开画布，检查节点是否完整（正常应有 **20 个节点、29 条连线**）

> 若提示“DSL 版本差异”，直接确认即可；不要手工删除节点。

---

## 3. 配置模型（必须）

画布中有 **13 个节点**需要选择模型：

| 节点 | 数量 | 建议模型 | 温度 |
|---|---|---|---|
| 问题分类器 | 1 | deepseek-chat / deepseek-flash | 0.1 |
| 11 个业务参数提取 LLM | 11 | 同上 | 0.2 |
| 结果整理 | 1 | 同上 | 0.3 |

操作：
1. 逐个点击节点 → 右上角模型下拉框 → 选择已配置的模型
2. 或用画布多选 LLM 节点后批量设置（若当前版本支持）
3. 保存后确认无“模型未配置”红色提示

> 模型名/IP 属于部署配置，不写进 Git；不要把 API Key 填到提示词里。

---

## 4. 配置知识库（可选，但建议）

1. 先创建 **员工受众** 知识库（公司信息、业务流程、入职制度、FAQ）
2. 回到画布，点击 **员工知识库检索** 节点
3. 选择该知识库（`dataset_ids` 导入时为空属正常）
4. `top_k` 默认 4；无文档时可先跳过，节点会返回空结果，LLM 会回答“资料不足”

> ⚠️ 员工知识库不要混入访客/学生受众文档；投诉正文与心理记录不得作为知识库文档。

---

## 5. 发布与获取 API Key

1. 右上角 **发布 / Publish**
2. 进入 **访问 API**（API Access）
3. 创建 API Key（只显示一次，立即复制）
4. 把 Key 写入后端 `backend/.env`：

```ini
DIFY_BASE_URL=http://8.138.150.132
DIFY_ENTERPRISE_KEY=app-xxxxxxxxxxxxxxxx
DIFY_MODE=live
```

> `DIFY_MODE=mock` 时不调用 Dify，使用后端离线样本；联调时切 `live`。

---

## 6. 联调验证（后端）

### 6.1 直接调 Dify

```bash
curl -X POST "http://8.138.150.132/v1/workflows/run" \
  -H "Authorization: Bearer $DIFY_ENTERPRISE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {"payload_json": "{\"message\":\"查客户张三\",\"actor\":{\"id\":\"1\",\"real_name\":\"测试\"}}"},
    "response_mode": "blocking",
    "user": "1"
  }'
```

期望：`data.outputs.output_json` 是一段 JSON 字符串，含 `intent`、`params`、`draft`、`missing_fields`、`answer`。

### 6.2 走后端 API029

```bash
# 先登录拿 token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"advisor01","password":"test123"}'

# 企业助手
curl -X POST http://localhost:8000/api/v1/assistants/employee/messages \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message_id":"11111111-1111-1111-1111-111111111111","message":"查客户张三"}'
```

期望：`data.answer` 为文本；写操作请求返回 `data.proposal`（含 `confirmationToken`），数据库零写入。

---

## 7. 验收清单

- [ ] 导入后 20 节点 / 29 连线
- [ ] 13 个模型节点均已选模型
- [ ] 知识库节点已绑定（或明确暂不绑定）
- [ ] 直接调 Dify 返回合法 `output_json`
- [ ] 后端 mock 模式测试全过（`pytest tests/test_assistant.py`）
- [ ] 切 live 后“查客户/待办/统计”三类问题回答正确
- [ ] 写操作只出提议，确认后由普通接口执行
- [ ] 越权/敏感问题被拒绝或降级

---

## 8. 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 导入后模型节点空白 | DSL 不含 key/模型 | 按第 3 节逐个选择模型 |
| 知识检索节点报“未配置” | dataset_ids 为空 | 绑定员工知识库 |
| `output_json` 不是合法 JSON | 模型未按提示输出 | 检查提取器提示词是否被改；必要时降低温度 |
| 后端 503 AI_UNAVAILABLE | key 未配/网络不通 | 检查 `.env` 与出站网络 |
| 意图总是 OTHER | 分类器/提取器提示词被改 | 重新导入 DSL，不要手工删改 |
| 写操作被拒 400 | 确认 token 过期（5 分钟）或内容被改 | 重新让助手生成提议 |
