"""Short-lived shared state, isolated from business transactions and never logged."""
import json
from sqlalchemy import text
from app.db.session import engine

def get(key):
    with engine.begin() as conn:
        return conn.scalar(text('SELECT value FROM runtime_state WHERE key=:k AND expires_at>now()'),{'k':key})

def put(key,value,ttl=900,merge=False):
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM runtime_state WHERE expires_at<now()'))
        row=conn.execute(text("INSERT INTO runtime_state(key,value,expires_at) VALUES (:k,CAST(:v AS jsonb),now()+:ttl*interval '1 second') ON CONFLICT(key) DO UPDATE SET value=CASE WHEN :merge AND runtime_state.expires_at>now() THEN runtime_state.value || EXCLUDED.value ELSE EXCLUDED.value END,expires_at=EXCLUDED.expires_at RETURNING value"),{'k':key,'v':json.dumps(value,ensure_ascii=False),'ttl':ttl,'merge':merge}).scalar_one()
        return row

def drop(key):
    with engine.begin() as conn:conn.execute(text('DELETE FROM runtime_state WHERE key=:k'),{'k':key})
