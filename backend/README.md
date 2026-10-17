# 后端交付入口

正式启动入口：app.main:app。Python3.12，PostgreSQL15及以上；当前真实验证服务器为15.19。

安装：python -m pip install -r requirements.lock.txt

配置：从.env.example和.env.test.example分别配置本机业务库与独立测试库；实际.env文件不要提交。

迁移：python -m app.db.migrate

首次管理员：python -m scripts.bootstrap_admin --username admin --password-file bootstrap.credentials.txt

启动：python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

测试：python -m scripts.test_backend -q --tb=short。不要直接对正式库运行pytest。

完整说明：

- ../docs/后端交付与运行手册.md
- ../docs/后端阶段验收与问题闭环.md
- ../docs/后续前端对接变更清单.md
- ../docs/Dify业务契约与联调说明.md
- ../docs/openapi.json

本轮日报只记录普通工作，心理和投诉明细留在专项模块。Dify/ASR默认关闭，可先通过标准业务接口操作。真实外部集成、容器启动和完整备份恢复验收状态见阶段记录。
