"""Create the first admin; credentials are written once to a private local file."""
import argparse,os
from pathlib import Path
from datetime import datetime,timedelta,timezone
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.user import SysUser
from app.core.security import generate_temp_password,hash_password

def bootstrap(username,password_file):
    target=Path(password_file).resolve()
    if not target.parent.is_dir():raise RuntimeError('Credential directory must exist')
    with SessionLocal.begin() as db:
        if db.scalar(select(SysUser.id).where(SysUser.employee_role=='ADMIN')):raise RuntimeError('An administrator already exists; use password reset')
        plain=generate_temp_password(20)
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as output:output.write('username='+username+'\npassword='+plain+'\n')
            db.add(SysUser(username=username,password_hash=hash_password(plain),real_name='系统管理员',user_type='EMPLOYEE',employee_role='ADMIN',dept_id=None,status='NORMAL',must_change_password=True,temporary_password_expires_at=datetime.now(timezone.utc)+timedelta(days=7),token_version=0))
            db.flush()
        except Exception:
            target.unlink(missing_ok=True)
            raise
    return str(target)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--username',default='admin');parser.add_argument('--password-file',required=True);args=parser.parse_args()
    print('Administrator created. Read credentials locally:',bootstrap(args.username,args.password_file))
