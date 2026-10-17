"""Versioned, checksummed PostgreSQL migrations. No implicit destructive reset."""
import hashlib
from pathlib import Path
from sqlalchemy import text
from app.db.session import engine

DIRECTORY = Path(__file__).resolve().parents[2] / "migrations"

def migrate(connection=None):
    if connection is None:
        with engine.begin() as conn:
            return migrate(conn)
    connection.execute(text("SELECT pg_advisory_xact_lock(910100)"))
    connection.exec_driver_sql("CREATE TABLE IF NOT EXISTS yue_schema_version (version text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())")
    installed = dict(connection.execute(text("SELECT version, checksum FROM yue_schema_version")).all())
    applied = []
    for path in sorted(DIRECTORY.glob("*.sql")):
        source = path.read_text(encoding="utf-8-sig")
        digest = hashlib.sha256(source.encode()).hexdigest()
        if path.stem in installed:
            if installed[path.stem] != digest:
                raise RuntimeError("已执行的迁移文件内容变更: " + path.name)
            continue
        connection.exec_driver_sql(source)
        connection.execute(text("INSERT INTO yue_schema_version(version,checksum) VALUES (:v,:c)"), {"v":path.stem,"c":digest})
        applied.append(path.stem)
    return applied

if __name__ == "__main__":
    print("Applied migrations:", migrate())
