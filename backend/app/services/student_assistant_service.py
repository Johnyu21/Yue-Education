"""Student assistant: model proposes, backend authorizes, user confirms through normal APIs."""
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import ValidationError
from app.core.confirmation import sign_confirmation
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.transaction import with_business_transaction
from app.integrations.dify import call_student_workflow
from app.repositories import student_repo
from app.schemas.assistant import AssistantResult, Proposal, SourceItem, WfStudentOutput
from app.schemas.service import ServiceCreateRequest
from app.schemas.feedback import FeedbackCreateRequest
from app.services import psych_service, student_service, feedback_service, academic_service, m2_config


def handle_student_message(db,user,req,auth_token=None):
    if not user.is_student:raise ForbiddenError("仅学生可使用学生助手")
    actor_id=user.id
    profile=student_repo.get_profile_by_user(db,actor_id)
    if profile is None:raise NotFoundError("学生档案不存在")
    received=datetime.now(timezone.utc)
    consent=profile.psych_consent_status=="GRANTED"
    if consent:
        word=psych_service.detect_direct_word(req.message)
        if word:
            with with_business_transaction(db):
                psych_service.record_direct_risk(db,profile,source_event_key=psych_service._sub_key(str(req.message_id),"direct"),received_at=received,matched_word=word)
    payload={"schema_version":"1.0","message":req.message,"message_id":str(req.message_id),
        "conversation_id":req.conversation_id,"input_kind":req.input_kind,"observe_emotion":consent,
        "context":req.context.model_dump() if req.context else None}
    db.rollback()
    def result(answer,**kwargs):
        return AssistantResult(conversationId=req.conversation_id,messageId=str(req.message_id),answer=answer,**kwargs)
    try:
        wf=WfStudentOutput.model_validate(call_student_workflow(payload,actor_id))
    except (AppError,ValidationError,ValueError,TypeError):
        return result("AI服务暂不可用，请使用业务表单办理。",aiStatus="UNAVAILABLE")
    profile=student_repo.get_profile_by_user(db,actor_id)
    if profile.psych_consent_status=="GRANTED" and wf.observation and wf.observation.emotion_state!="UNKNOWN":
        with with_business_transaction(db):
            psych_service.record_dify_observation(db,profile,source_event_key=psych_service._sub_key(str(req.message_id),"emotion"),received_at=received,
                emotion_state=wf.observation.emotion_state,confidence=wf.observation.confidence)
    status="MOCK" if m2_config.dify_mode()=="mock" else "LIVE"
    try:
        if wf.intent=="PROFILE_QUERY":return result(student_service.get_self_overview(db,user).model_dump_json(),aiStatus=status)
        if wf.intent in {"SCORE_QUERY","SCHEDULE_QUERY","CASE_QUERY"}:
            handler={"SCORE_QUERY":academic_service.list_scores,"SCHEDULE_QUERY":academic_service.list_schedules,"CASE_QUERY":academic_service.list_application_cases}[wf.intent]
            rows,total=handler(db,user,page=1,page_size=20)
            import json
            return result(json.dumps({"items":[x.model_dump(mode="json") for x in rows],"total":total},ensure_ascii=False),aiStatus=status)
        if wf.intent=="ASSESSMENT_QUERY":
            import json
            from fastapi.encoders import jsonable_encoder
            return result(json.dumps(jsonable_encoder(academic_service.get_initial_assessment(db,user)),ensure_ascii=False),aiStatus=status)
        draft=wf.draft or {};key=str(uuid4());operation=None
        if wf.intent=="SERVICE_DRAFT":
            data=ServiceCreateRequest(**{**draft,"request_key":key,"confirmed":True})
            preview=student_service.canonical_service_payload(data);operation="SUBMIT_SERVICE"
        elif wf.intent=="FEEDBACK_DRAFT":
            data=FeedbackCreateRequest(**{**draft,"request_key":key,"confirmed":True})
            preview=feedback_service.canonical_feedback_payload(data);operation="SUBMIT_FEEDBACK"
        elif wf.intent=="UPGRADE_INTEREST":
            from app.schemas.student import UpgradeInterestRequest
            data=UpgradeInterestRequest(**{**draft,"request_key":key,"confirmed":True})
            project=student_repo.get_project(db,data.course_project_id)
            if project is None or not project.is_published:raise NotFoundError("项目不存在")
            preview={"course_project_id":data.course_project_id,"note":data.note};operation="UPGRADE_INTEREST"
        if operation:
            token=sign_confirmation(user,operation,entity_id=None,payload=preview,expected_version=None,request_key=key)
            from datetime import timedelta
            proposal=Proposal(operation=operation,preview=preview,requestKey=key,confirmationToken=token,expiresAt=received+timedelta(minutes=5))
            return result("请核对确认卡，确认后才会提交。",proposal=proposal,aiStatus=status)
        if wf.intent not in {"FAQ","OTHER",None}:return result("暂不支持该业务，请使用表单。",aiStatus=status)
        sources=[SourceItem(documentId=s.get("document_id",s.get("documentId")),title=s.get("title"),section=s.get("section")) for s in wf.sources]
        return result(wf.answer or "请描述您的问题。",sources=sources,missingFields=wf.missing_fields,aiStatus=status)
    except ValidationError as exc:
        return result("请补全业务信息后再确认。",missingFields=[str(e['loc'][0]) for e in exc.errors()],aiStatus=status)
    except AppError as exc:return result(exc.message,warnings=[exc.code],aiStatus=status)
