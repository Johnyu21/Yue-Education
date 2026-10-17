"""Transactional PostgreSQL reminder scans; one lease and one write transaction."""
import logging
import threading
from datetime import datetime,timezone
from functools import wraps
from zoneinfo import ZoneInfo
from sqlalchemy import text
from app.db.session import SessionLocal
from app.core.config import settings
from app.core.notification import notify

logger=logging.getLogger(__name__)
LOCK_IDS={'schedule_reminder':910001,'followup_reminder':910002}
_stop=threading.Event()
_threads=[]
_running=False


def with_advisory_lock(lock_id,name):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            with SessionLocal() as db:
                try:
                    with db.begin():
                        if not db.scalar(text('SELECT pg_try_advisory_xact_lock(:id)'),{'id':lock_id}):return 0
                        return fn(db,*args,**kwargs)
                except Exception:
                    logger.exception('Reminder scan failed: %s',name)
                    raise
        return wrapped
    return decorate


@with_advisory_lock(LOCK_IDS['schedule_reminder'],'schedule_reminder')
def scan_schedule_reminders(db):
    now=datetime.now(timezone.utc)
    rows=db.execute(text("""
        SELECT s.*,sp.user_id AS recipient FROM student_academic_schedule s
        JOIN student_profile sp ON sp.id=s.student_profile_id
        WHERE s.status='SCHEDULED' AND s.remind_at<=:now
        AND NOT EXISTS (SELECT 1 FROM notification n WHERE n.recipient_user_id=sp.user_id
          AND n.business_event_key='schedule:'||s.id||':reminder:'||s.reminder_revision)
        ORDER BY s.remind_at,s.id LIMIT 200 FOR UPDATE OF s SKIP LOCKED
    """),{'now':now}).mappings().all()
    sent=0
    for row in rows:
        when=row['start_at'].astimezone(ZoneInfo(settings.business_timezone))
        sent+=len(notify(db,f"schedule:{row['id']}:reminder:{row['reminder_revision']}",[row['recipient']],category='SYSTEM',
            title='日程提醒：'+row['title'],content=f"日程时间：{when:%Y-%m-%d %H:%M}",related_type=None,related_id=None))
    return sent


@with_advisory_lock(LOCK_IDS['followup_reminder'],'followup_reminder')
def scan_followup_reminders(db):
    now=datetime.now(timezone.utc)
    rows=db.execute(text("""
        SELECT l.* FROM crm_lead l WHERE l.next_follow_up_at<=:now AND l.owner_user_id IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM notification n WHERE n.recipient_user_id=l.owner_user_id
         AND n.business_event_key='lead:'||l.id||':followup:'||floor(extract(epoch FROM l.next_follow_up_at))::bigint)
        ORDER BY l.next_follow_up_at,l.id LIMIT 200 FOR UPDATE OF l SKIP LOCKED
    """),{'now':now}).mappings().all()
    sent=0
    for row in rows:
        key=f"lead:{row['id']}:followup:{int(row['next_follow_up_at'].timestamp())}"
        sent+=len(notify(db,key,[row['owner_user_id']],category='SYSTEM',title='客户跟进提醒',
            content='计划跟进时间已到，请查看工作台。',related_type='lead',related_id=row['id']))
    return sent


def run_periodically(task,interval=60,name=''):
    def loop():
        while not _stop.is_set():
            try:task()
            except Exception:logger.exception('Scheduled task failed: %s',name)
            _stop.wait(max(1,interval))
    thread=threading.Thread(target=loop,daemon=True,name=name or task.__name__)
    thread.start();_threads.append(thread)
    return thread


def start_all(interval=60):
    global _running
    if _running:return
    _running=True;_stop.clear()
    run_periodically(scan_schedule_reminders,interval,'schedule_reminder')
    run_periodically(scan_followup_reminders,interval*2,'followup_reminder')


def stop_all():
    global _running
    _stop.set()
    for thread in _threads:thread.join(timeout=1)
    _threads.clear();_running=False
