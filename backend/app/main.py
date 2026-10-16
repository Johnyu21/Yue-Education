"""
应用入口（M1-03）

作用：组装应用。不写业务逻辑。
启动：uvicorn app.main:app --reload --port 8000
"""
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.responses import (
    setup_exception_handlers,
    setup_request_id,
    ok,
    fail,
)
from app.db.session import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title=settings.app_name, version="1.0.0")

# 装配公共能力
setup_request_id(app)
setup_exception_handlers(app)

# =============================================================
# 注册路由（⚠️ 由 M1 一次性注册好，各模块不用动本文件）
# 按「资源」分文件：一个业务概念一个文件，跨角色共用
from app.controllers import auth as c_auth                 # 认证
from app.controllers import organization as c_org           # 组织/账号/通知/文件
from app.controllers import public as c_public              # 公开门户
from app.controllers import assistants as c_assist          # 智能助手
from app.controllers import leads as c_leads                # 线索与研判
from app.controllers import students as c_students          # 学生管理
from app.controllers import services as c_services          # 行政服务
from app.controllers import feedback as c_feedback          # 售后工单
from app.controllers import psych as c_psych                # 心理关怀
from app.controllers import daily_reports as c_daily        # 员工日报
from app.controllers import workbench as c_workbench        # 工作台
from app.controllers import reports as c_reports            # 智能报告

for _r in (c_auth, c_org, c_public, c_assist, c_leads, c_students,
           c_services, c_feedback, c_psych, c_daily, c_workbench, c_reports):
    app.include_router(_r.router)


# =============================================================
# 定时任务（M1-09）—— 默认关闭，用 SCHEDULER_ENABLED=true 开
# ⚠️ 多实例部署时只在其中一个开（内部有 advisory lock 兜底）
# =============================================================
@app.on_event("startup")
def _start_scheduler():
    if settings.scheduler_enabled:
        from app.core.scheduler import start_all
        start_all(settings.scheduler_interval)
        logging.info("定时任务已启动（间隔 %s 秒）", settings.scheduler_interval)
    else:
        logging.info("定时任务未启用（SCHEDULER_ENABLED=false）")


@app.get("/api/v1/health/live")
def health_live():
    """进程存活（API001）：能返回就说明服务活着。"""
    return ok({"status": "up"})


@app.get("/api/v1/health/ready")
def health_ready():
    """依赖就绪（API002）：检查数据库通不通。"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    if not db_ok:
        return JSONResponse(status_code=503, content=fail("AI_UNAVAILABLE", "数据库不可用"))
    return ok({"status": "up", "database": True})
