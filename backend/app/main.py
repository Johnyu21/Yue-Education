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
# —— 这样避免五个人同时改 main.py 产生冲突
# =============================================================
from app.controllers import auth as auth_router            # M1 认证
from app.controllers import organization as org_router      # M1 组织管理
from app.controllers import public as public_router          # M2 访客客服与研判
from app.controllers import employee as employee_router      # M3 企业助手
from app.controllers import student as student_router        # M4 学生助手
from app.controllers import reports as reports_router        # M5 智能报告

app.include_router(auth_router.router)
app.include_router(org_router.router)
app.include_router(public_router.router)
app.include_router(employee_router.router)
app.include_router(student_router.router)
app.include_router(reports_router.router)


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
