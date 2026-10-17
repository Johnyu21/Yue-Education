# 粤教服务前端

实验版页面已移植到正式项目，并按正式后端契约适配。保留访客页面、图片轮播和宣传视频，新增员工、学生、管理及报告的实际业务入口。

## 日常一键运行

双击项目根目录的一键启动.cmd即可启动前后端并打开网页；结束使用时双击一键停止.cmd。桌面已放置对应的启动/停止入口。见 ../docs/一键运行说明.md。

## 本地运行

后端入口为 app.main:app，默认监听 127.0.0.1:8000。使用已配置好的 backend/.env；此次前端移植不需要修改数据库结构。

在 frontend 目录执行：

~~~powershell
npm ci
npm run dev
~~~

浏览 http://127.0.0.1:5173/ 。使用管理员分配的正式账号，首次登录按提示改密。本批14个测试账号已按用户要求另行初始化到正式开发库，见 ../docs/Dify配置与正式项目测试账号使用说明.md。自动测试仍使用独立隔离数据。

后端不在本机8000端口时，在 frontend/.env.local 中设置 BACKEND_PROXY_TARGET=http://后端地址:端口；重启 Vite。默认浏览器请求 /api/v1，开发代理 /api。独立部署时配置同源 /api 反向代理，或通过 VITE_API_BASE_URL 指定完整 API 基址。

Dify 和 ASR 由后端连接，前端不保存应用密钥。启用方式见 docs/Dify业务契约与联调说明.md；未启用时显示真实不可用状态，表单和确定性统计继续工作。

## 代码位置

- src/App.vue：登录、岗位菜单、日报、报告及应用外壳。
- src/VisitorPages.vue、VisitorPromoVideo.vue、VisitorGallery.vue、public/：访客页面与素材。
- src/api/client.ts：唯一 HTTP 客户端、JWT、统一响应、请求编号、写入幂等和错误处理。
- src/api/backend-contract.json：正式后端 OpenAPI 快照；修改接口时同步并运行审计。
- src/api/resources.ts：业务板块、接口路径、操作按钮和权限配置。
- src/components/BusinessWorkspace.vue、OperationForm.vue、SchemaField.vue：列表、详情及按后端字段生成的业务表单。
- src/components/AssistantDock.vue：访客、企业员工和学生助手。
- src/Assistant.vue、assistants.ts：日报收集助手及报告生成接口。
- src/api/proposals.ts：助手确认卡与正式写入接口的精确映射。
- src/api/domain.ts：日报和报告提交约束。

## 检查命令

~~~powershell
npm run build
npm test
npm run audit:api
npm run test:browser
~~~

前三项分别检查构建与类型、组件与契约、接口入口映射。test:browser 使用 backend/.env.test，仅允许 ENVIRONMENT=test、TEST_DATABASE_ENABLED=true 且数据库名以 _test 结尾；在随机 test_ schema 中创建合成账号和业务资料，自动启动独立端口的后端与 Vite，完成后清理该 schema 和私有附件。不会向正式业务库写入演示数据。测试启动前还检查专属隔离标记，不能拿正式站点地址运行。

浏览器测试使用已安装的 Microsoft Edge；没有 Edge 时需安装 Playwright Chromium。默认 Python 为 backend/.venv/Scripts/python.exe，可用 UI_QA_PYTHON 指定替代路径。结果与截图在被 Git 忽略的 backend/logs/frontend-ui-qa/。

完整移植范围、后端获准修改和验证边界见 ../docs/前端移植与联调交付说明.md；接口逐项映射见 ../docs/前端接口对接清单.md。

2026-10-17补充：右上角个人设置/通知下拉、管理员账号中心、员工通讯录账号隐藏及7名学生演示资料，见 ../docs/账号菜单与演示数据更新说明.md 和 ../docs/演示账号与数据说明.md。
