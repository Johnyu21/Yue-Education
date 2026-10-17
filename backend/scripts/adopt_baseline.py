"""Adopt only a byte-equivalent structural baseline; never infer that old data was reviewed."""
import hashlib,uuid
from sqlalchemy import text
from app.db.session import engine
from app.db.migrate import DIRECTORY

def _signature(conn,schema,table):
    columns=conn.execute(text("SELECT a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,a.attidentity,coalesce(pg_get_expr(d.adbin,d.adrelid),'') FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE n.nspname=:s AND c.relname=:t AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum"),{'s':schema,'t':table}).all()
    constraints=conn.execute(text("SELECT pg_get_constraintdef(x.oid) FROM pg_constraint x JOIN pg_class c ON c.oid=x.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=:s AND c.relname=:t ORDER BY x.contype,pg_get_constraintdef(x.oid)"),{'s':schema,'t':table}).scalars().all()
    indexes=conn.execute(text('SELECT indexdef FROM pg_indexes WHERE schemaname=:s AND tablename=:t ORDER BY indexname'),{'s':schema,'t':table}).scalars().all()
    def normalize(value):return str(value).replace(schema+'.','').replace('"'+schema+'".','')
    return ([tuple(normalize(v) for v in row) for row in columns],sorted(normalize(v) for v in constraints),sorted(normalize(v) for v in indexes))

def adopt(conn,target):
    if not target.replace('_','').isalnum():raise RuntimeError('Invalid target schema')
    if conn.scalar(text("SELECT to_regclass(:t)"),{'t':target+'.yue_schema_version'}):raise RuntimeError('Version registry already exists; use normal migrations')
    reference='verify_'+uuid.uuid4().hex
    conn.execute(text('SELECT pg_advisory_xact_lock(910100)'))
    conn.exec_driver_sql('CREATE SCHEMA '+reference)
    conn.exec_driver_sql('SET LOCAL search_path TO '+reference)
    paths=[DIRECTORY/'001_initial.sql']
    conn.exec_driver_sql(paths[0].read_text(encoding='utf-8-sig'))
    m5=[conn.scalar(text('SELECT to_regclass(:t)'),{'t':target+'.'+name}) is not None for name in ('m5_daily','m5_report','m5_chat')]
    if any(m5) and not all(m5):raise RuntimeError('Partial M5 schema; reconcile before adoption')
    if all(m5):
        paths.append(DIRECTORY/'002_reports.sql');conn.exec_driver_sql(paths[-1].read_text(encoding='utf-8-sig'))
    tables=conn.execute(text('SELECT tablename FROM pg_tables WHERE schemaname=:s'),{'s':reference}).scalars().all()
    for name in tables:
        if _signature(conn,reference,name)!=_signature(conn,target,name):raise RuntimeError('Baseline structure mismatch: '+name)
    conn.exec_driver_sql('SET LOCAL search_path TO '+target)
    conn.exec_driver_sql('DROP SCHEMA '+reference+' CASCADE')
    conn.exec_driver_sql('CREATE TABLE yue_schema_version(version text PRIMARY KEY,checksum text NOT NULL,applied_at timestamptz NOT NULL DEFAULT now())')
    for p in paths:
        conn.execute(text('INSERT INTO yue_schema_version(version,checksum) VALUES (:v,:c)'),{'v':p.stem,'c':hashlib.sha256(p.read_text(encoding='utf-8-sig').encode()).hexdigest()})
    return [p.stem for p in paths]

if __name__=='__main__':
    from app.core.config import settings
    with engine.begin() as conn:print('Adopted:',adopt(conn,settings.postgres_schema))
