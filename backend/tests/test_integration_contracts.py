"""Regression tests for the integration audit; no external AI calls."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.core.confirmation import sign_confirmation, verify_confirmation
from app.core.errors import InvalidRequestError
from app.schemas.service import ServiceCreateRequest
from app.schemas.event import EventCreateIn
from app.services.assessment_rules import evaluate_project
from app.core import storage


def test_malformed_rules_never_match():
    p=SimpleNamespace(id=1,name="bad",admission_rules={"criteria":[42]},rule_approved_at=datetime.now(timezone.utc),rule_version="v1")
    assert evaluate_project(p,{})["decision"] == "NEEDS_INFO"


def test_confirmation_binds_actual_request_key():
    actor=SimpleNamespace(id=1)
    token=sign_confirmation(actor,"TEST",entity_id=None,payload={},expected_version=None,request_key="original")
    with pytest.raises(InvalidRequestError):
        verify_confirmation(actor,token,operation="TEST",entity_id=None,payload={},request_key="changed")


def test_unknown_write_fields_rejected():
    with pytest.raises(ValidationError):
        ServiceCreateRequest(request_key=uuid4(),service_type="OTHER",title="x",description="x",role="ADMIN")


def test_naive_business_datetime_rejected():
    with pytest.raises(ValidationError):
        EventCreateIn(title="x",description="x",organizer_user_id=1,host_department_id=1,
            start_at="2026-11-01T00:00:00",end_at="2026-11-02T00:00:00",signup_deadline="2026-10-30T00:00:00",capacity=1)


def test_storage_sibling_prefix_is_not_inside_root(tmp_path,monkeypatch):
    base=tmp_path/"store";base.mkdir()
    sibling=tmp_path/"store-private";sibling.mkdir()
    (sibling/"secret.pdf").write_bytes(b"secret")
    monkeypatch.setattr(storage,"_storage_root",lambda:base)
    assert storage.resolve_path("../store-private/secret.pdf") is None
