"""Restore only to an explicitly named empty *_recovery database and an empty folder."""
import argparse,json,shutil,subprocess,tarfile
from pathlib import Path
from sqlalchemy import create_engine,text
from sqlalchemy.engine import URL
from app.core.config import settings
from scripts.backup import digest,pg_environment

def restore(folder,target_database,files_output,pg_bin=None):
    if not target_database.endswith('_recovery') or target_database==settings.postgres_db:raise RuntimeError('Restore target must be a different *_recovery database')
    source=Path(folder).resolve();output=Path(files_output).resolve()
    manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    for name in ('database.dump','files.tar.gz'):
        if digest(source/name)!=manifest['sha256'][name]:raise RuntimeError('Backup checksum mismatch')
    if output.exists() and any(output.iterdir()):raise RuntimeError('File restore directory must be empty')
    target=create_engine(URL.create('postgresql+psycopg',username=settings.postgres_user,password=settings.postgres_password,host=settings.postgres_host,port=settings.postgres_port,database=target_database))
    try:
        with target.connect() as conn:
            if conn.scalar(text("SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')")):raise RuntimeError('Recovery database must be empty')
        exe=str(Path(pg_bin)/'pg_restore') if pg_bin else shutil.which('pg_restore')
        if not exe:raise RuntimeError('Install PostgreSQL pg_restore client')
        result=subprocess.run([exe,'--no-owner','--no-acl','--exit-on-error','--single-transaction','--dbname',target_database,str(source/'database.dump')],env=pg_environment(target_database),capture_output=True)
        if result.returncode:raise RuntimeError('pg_restore failed; original database was not touched')
        output.mkdir(parents=True,exist_ok=True)
        with tarfile.open(source/'files.tar.gz','r:gz') as archive:archive.extractall(output,filter='data')
        with target.connect() as conn:
            versions=dict(conn.execute(text('SELECT version,checksum FROM yue_schema_version')).all())
            if versions!=manifest['schema_versions']:raise RuntimeError('Restored migration versions do not match')
        return str(output)
    finally:target.dispose()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--target-database',required=True);p.add_argument('--files-output',required=True);p.add_argument('--pg-bin');a=p.parse_args()
    print('Restore verified:',restore(a.source,a.target_database,a.files_output,a.pg_bin))
