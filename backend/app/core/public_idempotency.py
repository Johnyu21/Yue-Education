import hashlib,json
from pydantic_core import to_jsonable_python
from sqlalchemy import text
from app.core.errors import StateConflictError

def reserve_public_request(db,operation,key,payload):
    fingerprint=hashlib.sha256(json.dumps(to_jsonable_python(payload),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    params={'o':operation,'k':str(key),'f':fingerprint}
    fresh=db.execute(text('INSERT INTO public_request(operation,request_key,fingerprint) VALUES (:o,CAST(:k AS uuid),:f) ON CONFLICT DO NOTHING RETURNING request_key'),params).first()
    actual=db.scalar(text('SELECT fingerprint FROM public_request WHERE operation=:o AND request_key=CAST(:k AS uuid)'),params)
    if actual!=fingerprint:raise StateConflictError('请求键已被其他内容使用')
    return bool(fresh)
