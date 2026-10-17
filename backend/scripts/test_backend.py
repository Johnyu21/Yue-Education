"""Run tests in a fresh schema of the explicitly configured dedicated test database.
Usage: python -m scripts.test_backend [pytest arguments]. Never reads production .env.
"""
import os
import re
import sys
from pathlib import Path
from uuid import uuid4
from dotenv import dotenv_values

BASE = Path(__file__).resolve().parents[1]

def main():
    values = dotenv_values(BASE / ".env.test")
    if not values or values.get("TEST_DATABASE_ENABLED") != "true":
        raise SystemExit("需要独立 .env.test 和 TEST_DATABASE_ENABLED=true")
    dbname = values.get("POSTGRES_DB", "")
    if not dbname.endswith("_test") or values.get("ENVIRONMENT") != "test":
        raise SystemExit("拒绝测试: 专用数据库必须以 _test 结尾且 ENVIRONMENT=test")
    for key,value in values.items():
        if value is not None:os.environ[key] = value
    schema = "test_" + uuid4().hex
    os.environ["POSTGRES_SCHEMA"] = schema
    os.environ["M5_AI_MODE"] = "DISABLED"
    os.environ["DIFY_MODE"] = "mock"
    from sqlalchemy import create_engine, text
    from app.core.config import settings
    from app.db.migrate import migrate
    admin = create_engine(settings.database_url, hide_parameters=True)
    try:
        with admin.begin() as c:
            c.exec_driver_sql('CREATE SCHEMA "' + schema + '"')
        with admin.begin() as c:migrate(c)
        import pytest
        code = pytest.main(sys.argv[1:] or ["-q"])
    finally:
        admin.dispose()
        from app.db.session import engine
        engine.dispose()
        if not re.fullmatch(r"test_[a-f0-9]{32}", schema):raise RuntimeError("非法测试 schema")
        with admin.begin() as c:c.exec_driver_sql('DROP SCHEMA "' + schema + '" CASCADE')
        admin.dispose()
    return code

if __name__ == "__main__":
    raise SystemExit(main())
