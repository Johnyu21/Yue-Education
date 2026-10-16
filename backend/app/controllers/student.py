"""
M4 · 学生助手 —— 接口骨架（待实现）

负责人：M4
内容：学生工作台、行政服务（请假/考务）、售后（学生侧）、心理、教务与进度

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
本文件负责的接口（共 18 个）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  【学生本人】
   API046 GET   /api/v1/me/student-profile               我的档案
   API050 GET   /api/v1/services                         行政申请列表
   API051 GET   /api/v1/services/{id}                    申请详情
   API052 POST  /api/v1/services                         提交请假/考务（ⓒ）
   API053 POST  /api/v1/services/{id}/cancel             撤销申请
   API056 GET   /api/v1/me/feedback-tickets              我的工单
   API057 POST  /api/v1/me/feedback-tickets              提投诉/建议（ⓒ）
   API058 GET   /api/v1/me/feedback-tickets/{id}         工单详情
   API063 POST  /api/v1/me/feedback-tickets/{id}/confirm 确认关闭
   API064 POST  /api/v1/me/feedback-tickets/{id}/reopen  不认可，重新打开
   API065 POST  /api/v1/me/feedback-tickets/{id}/rating  评价 1~5 分
   API073 GET   /api/v1/me/scores                        我的成绩
   API076 GET   /api/v1/me/schedules                     我的日程（DDL/考试）
   API077 PUT   /api/v1/me/schedules/{id}/reminder       设置提醒
   API078 GET   /api/v1/application-cases                我的申请进度
   API079 GET   /api/v1/application-cases/{case_no}/timeline  进度时间线

  【心理】
   API066 PUT  /api/v1/me/psych-consent                  心理授权同意/撤回
   API068 GET  /api/v1/employees/students/{id}/psych-observations  心理观测
   API069 POST /api/v1/employees/students/{id}/psych-corrections   人工修正
   API070 GET  /api/v1/employees/psych-alerts            预警列表
   API071 GET  /api/v1/employees/psych-alerts/{id}       预警详情
   API072 POST /api/v1/employees/psych-alerts/{id}/actions  处置
   API093 GET  /api/v1/me/initial-assessment             入学评估

  【学生 -> 员工】
   API054 POST /api/v1/services/{id}/decision            审批（ⓥⓒ）
   API055 POST /api/v1/services/{id}/assignment          指派处理人
   API095 POST /api/v1/me/upgrade-interests              升学意向（增值转化）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ⓥ = 需要 expected_version    ⓒ = 需要 confirmation_token

⚠️ 实现要求：
  1. 学生只能看自己的数据 —— 用 scope 兜（范围外返回 404 不是 403）
  2. **心理数据是敏感的**：额外查 `can_see_psych()`（管理员也不自动有）
  3. 心理数据**不进通知正文、不进日志**
  4. 请假审批：状态更新与通知**同事务**
  5. 成绩表本轮只读（data_source='TEST'），不提供增删改

📖 参考：docs/ 下 M1-03 / M1-04 / M1-05 / M1-事务管理 / M1-确认令牌
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.errors import NotImplementedYetError
from app.core.responses import ok
from app.db.session import get_db
from app.models.user import SysUser

router = APIRouter(tags=["M4 · 学生助手"])


def _todo(api: str, who: str = "M4"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


# ---------------- 学生本人 ----------------

@router.get("/api/v1/me/student-profile")
def my_profile(user: SysUser = Depends(require_password_changed),
               db: Session = Depends(get_db)):
    """API046 我的档案"""
    _todo("API046")


@router.get("/api/v1/services")
def list_services(user: SysUser = Depends(require_password_changed),
                  db: Session = Depends(get_db)):
    """API050 行政申请列表（学生看自己，员工看授权范围）"""
    _todo("API050")


@router.get("/api/v1/services/{service_id}")
def get_service(service_id: int, user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API051 申请详情（scope.get_or_404）"""
    _todo("API051")


@router.post("/api/v1/services")
def create_service(user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API052 提交请假/考务

    ⚠️ LEAVE 必须 start_at < end_at（数据库会拒）
    ⚠️ 若由助手提议 → 校验 confirmation_token（ⓒ）
    """
    _todo("API052")


@router.post("/api/v1/services/{service_id}/cancel")
def cancel_service(service_id: int,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API053 撤销申请（仅待审批状态可撤销）"""
    _todo("API053")


@router.get("/api/v1/me/feedback-tickets")
def my_feedback_tickets(user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API056 我的工单"""
    _todo("API056")


@router.post("/api/v1/me/feedback-tickets")
def create_feedback_ticket(user: SysUser = Depends(require_password_changed),
                           db: Session = Depends(get_db)):
    """API057 提交投诉/建议

    ⚠️ priority 由后端按 category 决定（COMPLAINT→HIGH），**不接受客户端传入**
    """
    _todo("API057")


@router.get("/api/v1/me/feedback-tickets/{ticket_id}")
def get_feedback_ticket(ticket_id: int,
                        user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API058 工单详情（学生只看自己的）"""
    _todo("API058")


@router.post("/api/v1/me/feedback-tickets/{ticket_id}/confirm")
def confirm_feedback_ticket(ticket_id: int,
                            user: SysUser = Depends(require_password_changed),
                            db: Session = Depends(get_db)):
    """API063 学生确认关闭（写 closed_at）"""
    _todo("API063")


@router.post("/api/v1/me/feedback-tickets/{ticket_id}/reopen")
def reopen_feedback_ticket(ticket_id: int,
                           user: SysUser = Depends(require_password_changed),
                           db: Session = Depends(get_db)):
    """API064 不认可，RESOLVED → PROCESSING（保留前次解决记录）"""
    _todo("API064")


@router.post("/api/v1/me/feedback-tickets/{ticket_id}/rating")
def rate_feedback_ticket(ticket_id: int,
                         user: SysUser = Depends(require_password_changed),
                         db: Session = Depends(get_db)):
    """API065 满意度评价 1~5 分"""
    _todo("API065")


@router.get("/api/v1/me/scores")
def my_scores(user: SysUser = Depends(require_password_changed),
              db: Session = Depends(get_db)):
    """API073 我的成绩（只读）"""
    _todo("API073")


@router.get("/api/v1/me/schedules")
def my_schedules(user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API076 我的日程（DDL / 考试）"""
    _todo("API076")


@router.put("/api/v1/me/schedules/{schedule_id}/reminder")
def set_reminder(schedule_id: int,
                 user: SysUser = Depends(require_password_changed),
                 db: Session = Depends(get_db)):
    """API077 设置提醒（写 remind_at，不能晚于日程本身）"""
    _todo("API077")


@router.get("/api/v1/application-cases")
def my_application_cases(user: SysUser = Depends(require_password_changed),
                         db: Session = Depends(get_db)):
    """API078 我的申请进度"""
    _todo("API078")


@router.get("/api/v1/application-cases/{case_no}/timeline")
def application_timeline(case_no: str,
                         user: SysUser = Depends(require_password_changed),
                         db: Session = Depends(get_db)):
    """API079 进度时间线（按 sequence_no 排）"""
    _todo("API079")


@router.get("/api/v1/me/initial-assessment")
def my_initial_assessment(user: SysUser = Depends(require_password_changed),
                          db: Session = Depends(get_db)):
    """API093 入学评估"""
    _todo("API093")


@router.post("/api/v1/me/upgrade-interests")
def create_upgrade_interest(user: SysUser = Depends(require_password_changed),
                            db: Session = Depends(get_db)):
    """API095 升学意向（增值转化线索）"""
    _todo("API095")


# ---------------- 心理（⚠️ 最敏感）----------------

@router.put("/api/v1/me/psych-consent")
def set_psych_consent(user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API066 心理授权同意 / 撤回

    ⚠️ 授权状态 GRANTED 时必须同时写 consent_at + consent_version
    """
    _todo("API066")


@router.get("/api/v1/employees/students/{student_id}/psych-observations")
def psych_observations(student_id: int,
                       user: SysUser = Depends(require_password_changed),
                       db: Session = Depends(get_db)):
    """API068 心理观测（⚠️ 必须 can_see_psych + 班主任/顾问/主管/管理员）"""
    _todo("API068")


@router.post("/api/v1/employees/students/{student_id}/psych-corrections")
def psych_correction(student_id: int,
                     user: SysUser = Depends(require_password_changed),
                     db: Session = Depends(get_db)):
    """API069 人工修正情绪标签（⚠️ 仅主管/管理员 + 心理授权）"""
    _todo("API069")


@router.get("/api/v1/employees/psych-alerts")
def list_psych_alerts(user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API070 预警列表（⚠️ 需 can_see_psych）"""
    _todo("API070")


@router.get("/api/v1/employees/psych-alerts/{alert_id}")
def get_psych_alert(alert_id: int,
                    user: SysUser = Depends(require_password_changed),
                    db: Session = Depends(get_db)):
    """API071 预警详情"""
    _todo("API071")


@router.post("/api/v1/employees/psych-alerts/{alert_id}/actions")
def psych_alert_action(alert_id: int,
                       user: SysUser = Depends(require_password_changed),
                       db: Session = Depends(get_db)):
    """API072 预警处置（ⓥⓒ）

    ⚠️ 必须人工确认；DISMISSED/CLOSED 要填 closed_at + action_note
    ⚠️ 同一学生同时只能有一个未关闭预警（部分唯一索引）
    """
    _todo("API072")


# ---------------- 审批 ----------------

@router.post("/api/v1/services/{service_id}/decision")
def decide_service(service_id: int,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API054 审批请假/考务（ⓥⓒ）

    ⚠️ 状态更新 + 写通知 必须在同一事务
    ⚠️ 重复审批要返回 409（乐观锁兜）
    """
    _todo("API054")


@router.post("/api/v1/services/{service_id}/assignment")
def assign_service(service_id: int,
                   user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API055 指派处理人"""
    _todo("API055")
