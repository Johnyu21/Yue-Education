"""主键序列校准：把所有落后于 max(id) 的主键序列同步到 max(id)。

背景：demo_seed 等脚本用显式 id 插入数据后，自增序列仍停在旧值，
后续业务插入会撞主键，被统一翻译成“数据已存在（可能重复提交）”（409）。
在运行过显式 id 插入的种子脚本后执行本工具一次即可。

用法：backend/.venv/Scripts/python.exe tools/fix_sequences.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.stdout.reconfigure(encoding="utf-8")
import psycopg

from app.core.config import settings


def main() -> None:
    conn = psycopg.connect(
        settings.database_url.replace("postgresql+psycopg://", "postgresql://").split("?")[0])
    cur = conn.cursor()
    cur.execute("""
        SELECT sequencename, last_value FROM pg_sequences
        WHERE schemaname='public' AND sequencename LIKE '%\\_seq'
    """)
    fixed = []
    for name, last in cur.fetchall():
        table = name[:-4]
        try:
            cur.execute(f'SELECT COALESCE(MAX(id),0) FROM "{table}"')
            row = cur.fetchone()
            if row is None:
                continue
            mx = int(row[0])
            if last is not None and last < mx:
                cur.execute(f"SELECT setval('{name}', %s, true)", (mx,))
                fixed.append((name, int(last), mx))
        except Exception:
            continue
    conn.commit()
    print("校准的序列：")
    for name, old, new in fixed:
        print(f"  {name}: {old} -> {new}")
    if not fixed:
        print("  （无落后序列）")
    conn.close()


if __name__ == "__main__":
    main()
