ALTER TABLE m5_daily ALTER COLUMN report_date TYPE date USING report_date::date;
ALTER TABLE m5_daily ALTER COLUMN submitted_at TYPE timestamptz USING submitted_at::timestamptz;
ALTER TABLE m5_daily ALTER COLUMN updated_at TYPE timestamptz USING updated_at::timestamptz;
ALTER TABLE m5_daily ADD COLUMN required_capabilities jsonb NOT NULL DEFAULT '[]';
ALTER TABLE m5_daily ADD COLUMN approved_required_capabilities jsonb NOT NULL DEFAULT '[]';
ALTER TABLE m5_daily ADD COLUMN approved_version integer;
ALTER TABLE m5_daily ADD COLUMN approved_at timestamptz;
ALTER TABLE m5_report ALTER COLUMN dept_id DROP NOT NULL;
ALTER TABLE m5_report ALTER COLUMN start_date TYPE date USING start_date::date;
ALTER TABLE m5_report ALTER COLUMN end_date TYPE date USING end_date::date;
ALTER TABLE m5_report ALTER COLUMN created_at TYPE timestamptz USING created_at::timestamptz;
ALTER TABLE m5_report ALTER COLUMN updated_at TYPE timestamptz USING updated_at::timestamptz;
ALTER TABLE m5_report ADD COLUMN required_capabilities jsonb NOT NULL DEFAULT '[]';
ALTER TABLE m5_report ADD COLUMN snapshot_id varchar;
CREATE TABLE m5_daily_revision (
 id varchar PRIMARY KEY, daily_id varchar NOT NULL REFERENCES m5_daily(id), version integer NOT NULL,
 approved_by bigint NOT NULL REFERENCES sys_user(id), approved_at timestamptz NOT NULL,
 content jsonb NOT NULL, required_capabilities jsonb NOT NULL,
 UNIQUE(daily_id,version)
);
CREATE TABLE m5_report_snapshot (
 id varchar PRIMARY KEY, owner_id bigint NOT NULL REFERENCES sys_user(id),
 request_data jsonb NOT NULL, response_data jsonb NOT NULL,
 student_ids jsonb NOT NULL, required_capabilities jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE m5_report ADD CONSTRAINT fk_report_snapshot FOREIGN KEY(snapshot_id) REFERENCES m5_report_snapshot(id);
CREATE INDEX ix_report_snapshot_owner ON m5_report_snapshot(owner_id,created_at);
-- Existing free text predates the ordinary-daily policy; do not silently declassify it.
UPDATE m5_daily SET required_capabilities='["psych_access_enabled","can_handle_feedback"]',approved_required_capabilities='["psych_access_enabled","can_handle_feedback"]';
UPDATE m5_report SET required_capabilities='["psych_access_enabled","can_handle_feedback"]';
