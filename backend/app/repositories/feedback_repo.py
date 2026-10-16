"""
售后工单 查询（学生本人）
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feedback_ticket import StudentFeedbackTicket
from app.repositories.common import paginate


def list_tickets_by_student(db: Session, profile_id: int, *, status: str | None = None,
                            page: int = 1, page_size: int = 20):
    stmt = select(StudentFeedbackTicket).where(
        StudentFeedbackTicket.student_profile_id == profile_id)
    if status:
        stmt = stmt.where(StudentFeedbackTicket.status == status)
    stmt = stmt.order_by(StudentFeedbackTicket.create_time.desc(), StudentFeedbackTicket.id.desc())
    return paginate(db, stmt, page, page_size)


def get_ticket(db: Session, ticket_id: int) -> StudentFeedbackTicket | None:
    return db.get(StudentFeedbackTicket, ticket_id)


def get_ticket_by_request_key(db: Session, request_key) -> StudentFeedbackTicket | None:
    return db.scalar(select(StudentFeedbackTicket).where(
        StudentFeedbackTicket.request_key == request_key))
