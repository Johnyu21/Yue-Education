from fastapi import APIRouter,Depends
from app.core.deps import require_password_changed
from app.db.session import get_db
from app.core.responses import ok
from app.core.transaction import with_business_transaction
from app.schemas.academic_admin import ScoreWrite,ScheduleWrite
from app.services import academic_admin_service as svc
router=APIRouter(prefix='/api/v1/employees/students',tags=['教务维护'])

@router.post('/{student_id}/scores',status_code=201)
def create_score(student_id:int,data:ScoreWrite,user=Depends(require_password_changed),db=Depends(get_db)):
    with with_business_transaction(db):result=svc.create_score(db,user,student_id,data)
    return ok(result)

@router.put('/{student_id}/scores/{score_id}')
def update_score(student_id:int,score_id:int,data:ScoreWrite,user=Depends(require_password_changed),db=Depends(get_db)):
    with with_business_transaction(db):result=svc.update_score(db,user,student_id,score_id,data)
    return ok(result)

@router.post('/{student_id}/schedules',status_code=201)
def create_schedule(student_id:int,data:ScheduleWrite,user=Depends(require_password_changed),db=Depends(get_db)):
    with with_business_transaction(db):result=svc.create_schedule(db,user,student_id,data)
    return ok(result)

@router.put('/{student_id}/schedules/{schedule_id}')
def update_schedule(student_id:int,schedule_id:int,data:ScheduleWrite,user=Depends(require_password_changed),db=Depends(get_db)):
    with with_business_transaction(db):result=svc.update_schedule(db,user,student_id,schedule_id,data)
    return ok(result)
