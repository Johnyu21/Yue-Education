"""
M3 · 企业助手 —— 接口骨架（待实现）

负责人：M3
内容：CRM 客户管理、跟进、转学生、员工日报、员工处理台、申请单维护

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
本文件负责的接口（共 26 个）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  【线索 CRM】
   API032 GET   /api/v1/employees/leads                    线索列表（按范围）
   API033 GET   /api/v1/employees/leads/{id}               线索详情
   API034 POST  /api/v1/employees/leads                    员工录入线索
   API035 PATCH /api/v1/employees/leads/{id}               修改（乐观锁 ⓥ）
   API036 POST  /api/v1/employees/leads/{id}/claim         认领（条件更新）
   API037 POST  /api/v1/employees/leads/{id}/assignment    转派（主管）
   API038 GET   /api/v1/employees/leads/{id}/follow-ups    跟进列表
   API039 POST  /api/v1/employees/leads/{id}/follow-ups    新增跟进
   API040 POST  /api/v1/employees/leads/{id}/status        状态流转（乐观锁 ⓥ）

  【转学生】
   API043 POST  /api/v1/employees/leads/{id}/conversion    ⚠️ 5表事务（ⓒ）
   API044 POST  /api/v1/employees/students/{id}/enrollments
   API045 PATCH /api/v1/employees/students/{id}/enrollments/{eid}
   API049 PATCH /api/v1/employees/students/{id}/relationships

  【员工助手 / 语音】
   API029 POST /api/v1/assistants/employee/messages        企业助手
   API031 POST /api/v1/transcriptions                      语音转写

  【售后工单（员工侧）】
   API059 GET  /api/v1/employees/feedback-tickets          工单列表（需售后授权）
   API060 GET  /api/v1/employees/feedback-tickets/{id}     工单详情
   API061 POST /api/v1/employees/feedback-tickets/{id}/claim
   API062 POST /api/v1/employees/feedback-tickets/{id}/handling  处理（ⓥⓒ）

  【申请单维护】
   API080 POST /api/v1/employees/application-cases
   API081 POST /api/v1/employees/application-cases/{case_no}/events

  【员工日报】
   API082 GET  /api/v1/me/daily-reports
   API083 PUT  /api/v1/me/daily-reports/{report_date}      保存草稿
   API084 POST /api/v1/me/daily-reports/{report_date}/ai-draft  AI 生成草稿
   API085 POST /api/v1/me/daily-reports/{id}/submit        提交
   API086 POST /api/v1/employees/daily-reports/{id}/return 退回
   API087 GET  /api/v1/employees/daily-reports             主管查看

  【工作台】
   API088 GET /api/v1/workbench/todos                      待办（实时查询，不建表）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ⓥ = 需要 expected_version（乐观锁）
ⓒ = 需要 confirmation_token（确认令牌）

⚠️ 实现要求：
  1. 返回用 `ok(data)`；报错抛现成异常类
  2. 查数据必须 `build_scope(db, user, purpose)` —— ⚠️ 顾问只能看自己的客户
  3. 多表操作（转学生）必须用 `with_business_transaction`
  4. **AI 调用放事务外**（Dify 慢，别占锁）
  5. 转学生的临时密码**只在响应里出现一次**，不写日志

📖 参考：docs/ 下 M1-03 / M1-04 / M1-05 / M1-事务管理 / M1-确认令牌
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.errors import NotImplementedYetError
from app.core.responses import ok
from app.db.session import get_db
from app.models.user import SysUser

router = APIRouter(tags=["M3 · 企业助手"])


def _todo(api: str, who: str = "M3"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


# ---------------- 线索 CRM ----------------

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


@router.post("/api/v1/employees/leads")
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


@router.post("/api/v1/employees/leads/{lead_id}/follow-ups")
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


@router.post("/api/v1/employees/students/{student_id}/enrollments")
def add_enrollment(student_id: int, user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API044 添加课程关联"""
    _todo("API044")


@router.patch("/api/v1/employees/students/{student_id}/enrollments/{enrollment_id}")
def update_enrollment(student_id: int, enrollment_id: int,
                      user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API045 修改课程关联"""
    _todo("API045")


@router.patch("/api/v1/employees/students/{student_id}/relationships")
def update_student_relationship(student_id: int,
                                user: SysUser = Depends(require_password_changed),
                                db: Session = Depends(get_db)):
    """API049 修改学生关系（顾问/班级）"""
    _todo("API049")


# ---------------- 员工助手 / 语音 ----------------

@router.post("/api/v1/assistants/employee/messages")
def employee_assistant(user: SysUser = Depends(require_password_changed),
                       db: Session = Depends(get_db)):
    """API029 企业助手（受控意图，不直接写库）"""
    _todo("API029")


@router.post("/api/v1/transcriptions")
def transcribe(user: SysUser = Depends(require_password_changed)):
    """API031 语音转写（ASR）"""
    _todo("API031")


# ---------------- 售后工单（员工侧）----------------

@router.get("/api/v1/employees/feedback-tickets")
def list_feedback_tickets(user: SysUser = Depends(require_password_changed),
                          db: Session = Depends(get_db)):
    """API059 工单列表 —— ⚠️ 先查 can_handle_feedback，再按范围"""
    _todo("API059")


@router.get("/api/v1/employees/feedback-tickets/{ticket_id}")
def get_feedback_ticket(ticket_id: int,
                        user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API060 工单详情（需售后授权）"""
    _todo("API060")


@router.post("/api/v1/employees/feedback-tickets/{ticket_id}/claim")
def claim_feedback_ticket(ticket_id: int,
                          user: SysUser = Depends(require_password_changed),
                          db: Session = Depends(get_db)):
    """API061 认领工单"""
    _todo("API061")


@router.post("/api/v1/employees/feedback-tickets/{ticket_id}/handling")
def handle_feedback_ticket(ticket_id: int,
                           user: SysUser = Depends(require_password_changed),
                           db: Session = Depends(get_db)):
    """API062 处理工单（ⓥⓒ）

    ⚠️ RESOLVE 必填 resolution；状态与通知同事务（否则学生收不到）
    """
    _todo("API062")


# ---------------- 申请单维护 ----------------

@router.post("/api/v1/employees/application-cases")
def create_application_case(user: SysUser = Depends(require_password_changed),
                            db: Session = Depends(get_db)):
    """API080 创建申请单"""
    _todo("API080")


@router.post("/api/v1/employees/application-cases/{case_no}/events")
def append_application_event(case_no: str,
                             user: SysUser = Depends(require_password_changed),
                             db: Session = Depends(get_db)):
    """API081 追加申请进度（sequence_no 递增，不覆盖历史）"""
    _todo("API081")


# ---------------- 员工日报 ----------------

@router.get("/api/v1/me/daily-reports")
def my_daily_reports(user: SysUser = Depends(require_password_changed),
                     db: Session = Depends(get_db)):
    """API082 我的日报"""
    _todo("API082")


@router.put("/api/v1/me/daily-reports/{report_date}")
def save_daily_report(report_date: str,
                      user: SysUser = Depends(require_password_changed),
                      db: Session = Depends(get_db)):
    """API083 保存日报草稿（一人一天一份，重复提交是更新）"""
    _todo("API083")


@router.post("/api/v1/me/daily-reports/{report_date}/ai-draft")
def ai_draft_daily_report(report_date: str,
                          user: SysUser = Depends(require_password_changed)):
    """API084 AI 生成日报草稿（⚠️ 不写库，返回草稿让用户确认）"""
    _todo("API084")


@router.post("/api/v1/me/daily-reports/{report_id}/submit")
def submit_daily_report(report_id: int,
                        user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API085 提交日报"""
    _todo("API085")


@router.post("/api/v1/employees/daily-reports/{report_id}/return")
def return_daily_report(report_id: int,
                        user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API086 退回日报（主管）"""
    _todo("API086")


@router.get("/api/v1/employees/daily-reports")
def list_daily_reports(user: SysUser = Depends(require_password_changed),
                       db: Session = Depends(get_db)):
    """API087 查看本部门日报（主管）"""
    _todo("API087")


# ---------------- 工作台 ----------------

@router.get("/api/v1/workbench/todos")
def workbench_todos(user: SysUser = Depends(require_password_changed),
                    db: Session = Depends(get_db)):
    """API088 待办列表

    ⚠️ 实时查询（不建待办表）：待审批请假、待跟进线索、待处理工单
    """
    _todo("API088")


# ---------------- 骨架补齐（z 审核时发现遗漏）----------------

@router.get("/api/v1/employees/students")
def list_students(user: SysUser = Depends(require_password_changed),
                  db: Session = Depends(get_db)):
    """API047 学生列表（员工用）

    ⚠️ 本条在任务卡里没有负责人，需团队确认归属
    """
    _todo("API047", "未认领")


@router.get("/api/v1/employees/students/{student_id}")
def get_student(student_id: int,
                user: SysUser = Depends(require_password_changed),
                db: Session = Depends(get_db)):
    """API048 学生详情（员工用）

    ⚠️ 本条在任务卡里没有负责人，需团队确认归属
    """
    _todo("API048", "未认领")
