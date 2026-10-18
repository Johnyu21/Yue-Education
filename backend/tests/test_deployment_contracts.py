from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.security import create_access_token

def test_routes_have_no_duplicate_method_path():
    seen=set()
    for route in app.routes:
        for method in getattr(route,'methods',[]) or []:
            key=(method,route.path)
            assert key not in seen,key
            seen.add(key)

def test_ready_checks_schema_versions():
    with TestClient(app) as client:assert client.get('/api/v1/health/ready').status_code==200

def test_me_contains_current_capabilities(student):
    with TestClient(app) as client:
        response=client.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+create_access_token(student.id,student.token_version)})
        assert response.status_code==200,response.text
        assert response.json()['data']['isAdmin'] is False
        assert response.json()['data']['psychAccessEnabled'] is False

def test_production_rejects_default_secret():
    from app.core.config import Settings
    import pytest
    with pytest.raises(ValueError):Settings(_env_file=None,environment='prod',debug=False)


def test_naive_schedule_filter_is_rejected(student):
    with TestClient(app) as client:
        response=client.get('/api/v1/me/schedules?start_at=2026-10-01T00:00:00',headers={'Authorization':'Bearer '+create_access_token(student.id,student.token_version)})
        assert response.status_code==422,response.text


def test_m5_reads_shared_env_settings(monkeypatch):
    from app.services import m5_report_config
    from app.core.config import Settings
    monkeypatch.delenv('M5_AI_MODE',raising=False)
    shared=Settings(_env_file=None,postgres_password='synthetic-database-password',m5_ai_mode='DIFY',m5_dify_assistant_key='synthetic-key',m5_ai_timeout=12)
    monkeypatch.setattr(m5_report_config,'shared',shared)
    configured=m5_report_config.get_m5_settings()
    assert configured.ai_mode=='DIFY' and configured.assistant_key=='synthetic-key' and configured.ai_timeout==12
