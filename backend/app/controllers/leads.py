"""
线索 CRM 与研判 —— 线索增删改查 / 跟进 / 认领 / 转派 / 研判 / 转学生

⚠️ 实现要求：
  1. 统一响应：return ok(data)；报错抛 app.core.errors 里的异常类
  2. 需登录：Depends(require_password_changed)
  3. 查数据：用 build_scope(db, user, purpose) 限制范围（M1-05）
  4. 多表写：用 with_business_transaction（M1-S1）
  5. AI 调用**放事务外**（M1-S1）
  6. 每个接口下有 API 编号注释
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.errors import NotImplementedYetError
from app.core.responses import ok
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.lead import AssessmentIn, ResumeExtractionIn
from app.services import assessment_service

router = APIRouter(tags=["线索 CRM 与研判"])


def _todo(api: str, who: str = "M2/M3"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


@router.get("/api/v1/employees/leads")
def list_leads(user: SysUser = Depends(require_password_changed),
               db: Session = Depends(get_db)):
    """API032 线索列表 —— ⚠️ 必须按 scope 过滤"""
    _todo("API032")


@router.get("/api/v1/employees/leads/{lead_id}")
def get_lead(lead_id: int, user: SysUser = Depends(require_password_changed),
             db: Session = Depends(get_db)):
    """API033 线索详情 —— 用 scope.get_or_404"""
    _todo("API033")


@router.post("/api/v1/employees/leads", status_code=201)
def create_lead(user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API034 员工录入线索"""
    _todo("API034")


@router.patch("/api/v1/employees/leads/{lead_id}")
def update_lead(lead_id: int, user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API035 修改线索（ⓥ 乐观锁 version）"""
    _todo("API035")


@router.post("/api/v1/employees/leads/{lead_id}/claim")
def claim_lead(lead_id: int, user: SysUser = Depends(require_password_changed),
               db: Session = Depends(get_db)):
    """API036 认领线索

    ⚠️ 用条件更新：SET owner_user_id=? WHERE id=? AND owner_user_id IS NULL
       影响行数为 0 → 说明被别人抢了 → 抛 StateConflictError
    """
    _todo("API036")


@router.post("/api/v1/employees/leads/{lead_id}/assignment")
def assign_lead(lead_id: int, user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API037 转派（仅主管/管理员），须记录原因"""
    _todo("API037")


@router.get("/api/v1/employees/leads/{lead_id}/follow-ups")
def list_follow_ups(lead_id: int, user: SysUser = Depends(require_password_changed),
                    db: Session = Depends(get_db)):
    """API038 跟进记录列表"""
    _todo("API038")


@router.post("/api/v1/employees/leads/{lead_id}/follow-ups", status_code=201)
def add_follow_up(lead_id: int, user: SysUser = Depends(require_password_changed),
                  db: Session = Depends(get_db)):
    """API039 新增跟进"""
    _todo("API039")


@router.post("/api/v1/employees/leads/{lead_id}/status")
def update_lead_status(lead_id: int, user: SysUser = Depends(require_password_changed),
                       db: Session = Depends(get_db)):
    """API040 状态流转（ⓥ）

    ⚠️ SIGNED 必须带 signed_at；LOST 必须带 lost_at + loss_reason（数据库会拒）
    """
    _todo("API040")


# ---------------- 转学生（⚠️ 多表事务，最关键）----------------


@router.post("/api/v1/employees/leads/{lead_id}/assessments", status_code=201)
def assess_lead(lead_id: int,
                data: AssessmentIn,
                user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API041 执行研判（M2）

    流程：
      1. build_scope 检查能否操作这条客户（越权 → 404）
      2. 事务内写 RUNNING + assessment_request_id + started_at（版本 +1）
      3. ⚠️ **事务外**调 Dify 提取画像（不占数据库锁）
      4. 事务内按请求号**条件回写**报告（旧任务不会覆盖新结果）
    """
    return ok(assessment_service.assess_lead(db, user, lead_id, data))


@router.get("/api/v1/employees/leads/{lead_id}/assessment")
def get_lead_assessment(lead_id: int,
                        user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API042 取最近一份研判报告（失败但保留上一份成功报告时标 isPreviousReport）"""
    return ok(assessment_service.get_assessment(db, user, lead_id))


@router.post("/api/v1/employees/leads/{lead_id}/conversion")
def convert_lead(lead_id: int, user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API043 签约转学生 ⚠️ 5 表事务

    必须在 with_business_transaction 里同时完成：
      ① 建学生账号（student 类型，无 dept_id）
      ② 建学生档案（student_profile）
      ③ 建课程关联（student_course_enrollment）
      ④ 改线索状态 SIGNED + signed_at
      ⑤ 写跟进记录
    任一步失败 → 全部回滚。临时密码只在响应里出现一次（ⓒ）
    """
    _todo("API043")


@router.post("/api/v1/employees/leads/{lead_id}/resume-extraction")
def extract_resume(lead_id: int,
                   data: ResumeExtractionIn,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API096 简历文本/文件解析（M2）

    返回**可编辑的提取草稿**（含来源片段与缺失项），
    ⚠️ 不写正式客户事实、不改销售状态、不改研判状态；
    顾问核对后用 API035 PATCH 资料，再调 API041 开始正式研判。
    """
    return ok(assessment_service.extract_resume_draft(db, user, lead_id, data))

