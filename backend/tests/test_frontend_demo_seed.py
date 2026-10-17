"""Demo initialization stays additive and preserves existing account passwords."""
import pytest
from sqlalchemy import text
from scripts.seed_m5_frontend_demo import inspect, initialize
from app.core.security import hash_password


def test_demo_seed_is_complete_and_repeat_does_not_reset_passwords(m4_db):
    assert inspect(m4_db)['state']=='READY_TO_INSERT'
    created=initialize(m4_db)
    assert created['action']=='CREATED'
    assert created['account_count']==14
    assert m4_db.scalar(text('SELECT count(*) FROM student_profile WHERE is_demo=true'))==7
    custom_hash=hash_password('AlreadyChanged-2026!')
    m4_db.execute(text("UPDATE sys_user SET password_hash=:p WHERE username='ui_advisor'"),{'p':custom_hash})
    repeated=initialize(m4_db)
    assert repeated['action']=='SKIPPED_EXISTING'
    assert m4_db.scalar(text("SELECT password_hash FROM sys_user WHERE username='ui_advisor'"))==custom_hash
    assert m4_db.scalar(text('SELECT count(*) FROM sys_user'))==14
    m4_db.rollback()


def test_partial_username_conflict_aborts_without_filling_or_overwriting(m4_db):
    m4_db.execute(text("INSERT INTO sys_user(username,password_hash,real_name,user_type,employee_role) VALUES ('ui_admin',:p,'已有账号','EMPLOYEE','ADMIN')"),{'p':hash_password('ExistingUser-2026!')})
    assert inspect(m4_db)['state']=='CONFLICT'
    with pytest.raises(RuntimeError,match='conflict'):
        initialize(m4_db)
    assert m4_db.scalar(text('SELECT count(*) FROM sys_user'))==1
    assert m4_db.scalar(text("SELECT real_name FROM sys_user WHERE username='ui_admin'"))=='已有账号'
    assert m4_db.scalar(text('SELECT count(*) FROM sys_department'))==0
    m4_db.rollback()
