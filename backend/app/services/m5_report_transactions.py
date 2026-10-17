"""Service-owned unit of work, sharing the team's request Session."""
from fastapi import Depends
from app.db.session import get_db
from app.core.transaction import with_business_transaction

def m5_database(db=Depends(get_db)):
    with with_business_transaction(db):
        yield db
