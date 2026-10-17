"""
智能报告 —— 报告预览 / 学业评估

⚠️ 实现要求：
  1. 统一响应：return ok(data)；报错抛 app.core.errors 里的异常类
  2. 需登录：Depends(require_password_changed)
  3. 查数据：用 build_scope(db, user, purpose) 限制范围（M1-05）
  4. 多表写：用 with_business_transaction（M1-S1）
  5. AI 调用**放事务外**（M1-S1）
  6. 每个接口下有 API 编号注释
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.responses import ok
from app.db.session import get_db
from app.models.user import SysUser

router = APIRouter(tags=["智能报告"])




@router.post("/api/v1/me/academic-assessment")
def academic_assessment(user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API075 学业评估"""
    from sqlalchemy import select
    from app.core.errors import ForbiddenError
    from app.models.score import StudentScore
    from app.repositories.common import my_profile_id
    if not user.is_student:raise ForbiddenError("仅学生可查看本人学业评估")
    pid=my_profile_id(db,user)
    from app.core.config import settings
    query=select(StudentScore).where(StudentScore.student_profile_id==pid)
    if settings.environment=="prod":query=query.where(StudentScore.data_source!="TEST")
    rows=list(db.scalars(query))
    numeric=[float(r.score_numeric/r.max_score*100) for r in rows if r.score_type=='NUMERIC' and r.max_score]
    return ok({"numericCount":len(numeric),"otherCount":len(rows)-len(numeric),
        "averagePercent":round(sum(numeric)/len(numeric),2) if numeric else None,
        "dataStatus":"AVAILABLE" if numeric else "INSUFFICIENT_DATA",
        "aiStatus":"UNAVAILABLE","dataSources":sorted({r.data_source for r in rows}),
        "explanation":"仅将数值成绩按各自满分归一为百分比后计算平均，等级和通过制不混算。"})
