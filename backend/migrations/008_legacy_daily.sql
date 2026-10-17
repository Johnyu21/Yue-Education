-- Preserve every original row; imported submissions still require a real review.
CREATE TABLE legacy_daily_mapping (
 legacy_id bigint PRIMARY KEY REFERENCES employee_daily_report(id),
 daily_id varchar UNIQUE REFERENCES m5_daily(id), legacy_payload jsonb NOT NULL,
 imported_at timestamptz NOT NULL DEFAULT now()
);
DO $$
BEGIN
 IF EXISTS(SELECT 1 FROM employee_daily_report l JOIN m5_daily d ON d.user_id=l.employee_user_id AND d.report_date=l.report_date) THEN
  RAISE EXCEPTION 'Legacy/M5 daily date collision; reconcile before migration';
 END IF;
END $$;
INSERT INTO m5_daily(id,user_id,dept_id,report_date,original_text,content,status,return_reason,version,approved_snapshot,submitted_at,updated_at,required_capabilities)
SELECT md5('legacy_daily:'||id::text)::uuid::text,employee_user_id,dept_id,report_date,original_text,
 jsonb_build_object('work_summary',original_text,'items','[]'::jsonb,'difficulties','历史导入，请人工核对','next_plan',''),status,coalesce(return_reason,''),version,NULL,submitted_at,update_time,
 '["psych_access_enabled","can_handle_feedback"]'::jsonb
FROM employee_daily_report;
INSERT INTO legacy_daily_mapping(legacy_id,daily_id,legacy_payload)
SELECT id,md5('legacy_daily:'||id::text)::uuid::text,to_jsonb(l) FROM employee_daily_report l;
