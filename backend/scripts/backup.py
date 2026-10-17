"""Coordinated logical backup. Stop writes before running; never prints credentials."""
import argparse,hashlib,json,os,shutil,subprocess,tarfile
from pathlib import Path
from app.core.config import settings
from app.db.session import engine
from sqlalchemy import text

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def pg_environment(database=None):
    return {**os.environ,'PGHOST':settings.postgres_host,'PGPORT':str(settings.postgres_port),'PGUSER':settings.postgres_user,'PGPASSWORD':settings.postgres_password,'PGDATABASE':database or settings.postgres_db}

def backup(folder,pg_bin=None):
    folder=Path(folder).resolve();storage=Path(settings.file_storage_root).resolve()
    if folder.is_relative_to(storage):raise RuntimeError('Backup directory must be outside file storage')
    folder.mkdir(parents=True,exist_ok=False)
    exe=str(Path(pg_bin)/'pg_dump') if pg_bin else shutil.which('pg_dump')
    if not exe:raise RuntimeError('Install PostgreSQL client tools matching the server major version')
    args=[exe,'--format=custom','--no-owner','--no-acl','--exclude-table-data=*.runtime_state','--exclude-table-data=*.runtime_rate','--file',str(folder/'database.dump')]
    result=subprocess.run(args,env=pg_environment(),capture_output=True)
    if result.returncode:raise RuntimeError('pg_dump failed; check client/server compatibility and connection locally')
    with tarfile.open(folder/'files.tar.gz','w:gz') as archive:
        if storage.exists():archive.add(storage,arcname='storage',recursive=True)
    with engine.connect() as conn:
        versions=dict(conn.execute(text('SELECT version,checksum FROM yue_schema_version')).all())
        server=conn.scalar(text('SHOW server_version'))
    manifest={'database':settings.postgres_db,'server_version':server,'schema_versions':versions,'sha256':{n:digest(folder/n) for n in ('database.dump','files.tar.gz')}}
    (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    for file in folder.iterdir():file.chmod(0o600)
    return str(folder)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--pg-bin');a=p.parse_args()
    print('Backup created:',backup(a.output,a.pg_bin))
