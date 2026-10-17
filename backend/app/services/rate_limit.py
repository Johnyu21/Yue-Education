"""Shared token buckets. Forwarded addresses are accepted only from configured proxies."""
import hashlib
from sqlalchemy import text
from fastapi import Request
from app.core.config import settings
from app.db.session import engine
from app.services import m2_config
from app.services.m2_errors import RateLimitedError

def client_key(request:Request,purpose:str):
    peer=request.client.host if request.client else 'unknown'
    trusted={x.strip() for x in settings.trusted_proxy_ips.split(',') if x.strip()}
    forwarded=request.headers.get('x-forwarded-for')
    ip=forwarded.split(',')[0].strip() if forwarded and peer in trusted else peer
    return purpose+':'+ip

def check(key,rate=None):
    rate=m2_config.visitor_rate_limit_per_minute() if rate is None else rate
    if rate<=0:return
    digest=hashlib.sha256(key.encode()).hexdigest()
    allowed=False
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM runtime_rate WHERE updated_at<now()-interval '10 minutes'"))
        conn.execute(text('INSERT INTO runtime_rate(key,tokens,updated_at) VALUES (:k,:r,now()) ON CONFLICT DO NOTHING'),{'k':digest,'r':rate})
        row=conn.execute(text('SELECT tokens,EXTRACT(EPOCH FROM (clock_timestamp()-updated_at)) elapsed FROM runtime_rate WHERE key=:k FOR UPDATE'),{'k':digest}).one()
        tokens=min(float(rate),row.tokens+float(row.elapsed)*rate/60)
        allowed=tokens>=1
        conn.execute(text('UPDATE runtime_rate SET tokens=:t,updated_at=clock_timestamp() WHERE key=:k'),{'t':tokens-1 if allowed else tokens,'k':digest})
    if not allowed:raise RateLimitedError('请求过于频繁，请稍后再试')

def enforce(request,purpose):check(client_key(request,purpose))
