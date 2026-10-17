from fastapi import APIRouter,Depends
from app.core.deps import require_password_changed
from app.core.responses import ok
from app.core.transaction import with_business_transaction
from app.db.session import get_db
from app.schemas.lead_import import LeadImportIn
from app.services import lead_import_service as svc
router=APIRouter(prefix='/api/v1/employees/lead-imports',tags=['客户资料导入'])
@router.post('/preview')
def preview(data:LeadImportIn,user=Depends(require_password_changed),db=Depends(get_db)):
    return ok(svc.preview(db,user,data))
@router.post('/apply')
def apply(data:LeadImportIn,user=Depends(require_password_changed),db=Depends(get_db)):
    with with_business_transaction(db):result=svc.apply(db,user,data)
    return ok(result)
