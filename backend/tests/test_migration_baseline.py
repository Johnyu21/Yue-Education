from uuid import uuid4
from sqlalchemy import text,select
from app.db.session import engine
from app.db.migrate import DIRECTORY,migrate
from scripts.adopt_baseline import adopt

def test_exact_legacy_baseline_can_be_adopted_and_upgraded(monkeypatch,tmp_path):
    target='test_baseline_'+uuid4().hex
    with engine.begin() as c:
        c.exec_driver_sql('CREATE SCHEMA '+target)
        c.exec_driver_sql('SET LOCAL search_path TO '+target)
        c.exec_driver_sql((DIRECTORY/'001_initial.sql').read_text(encoding='utf-8-sig'))
        assert adopt(c,target)==['001_initial']
        assert len(migrate(c))==7
        assert migrate(c)==[]
        from sqlalchemy.orm import sessionmaker
        from scripts import bootstrap_admin
        from app.models.user import SysUser
        from app.core.security import verify_password
        factory=sessionmaker(bind=c)
        monkeypatch.setattr(bootstrap_admin,'SessionLocal',factory)
        credentials=tmp_path/'bootstrap.credentials.txt'
        bootstrap_admin.bootstrap('synthetic-admin',credentials)
        values=dict(line.split('=',1) for line in credentials.read_text(encoding='utf-8').splitlines())
        with factory() as session:
            admin=session.scalar(select(SysUser).where(SysUser.username=='synthetic-admin'))
            assert admin.must_change_password and admin.employee_role=='ADMIN'
            assert verify_password(values['password'],admin.password_hash)
        c.exec_driver_sql('DROP SCHEMA '+target+' CASCADE')
