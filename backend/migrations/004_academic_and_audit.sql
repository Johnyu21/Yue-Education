ALTER TABLE student_score DROP CONSTRAINT student_score_data_source_check;
ALTER TABLE student_score ADD CONSTRAINT student_score_data_source_check CHECK(data_source IN ('TEST','MANUAL'));
ALTER TABLE student_academic_schedule DROP CONSTRAINT student_academic_schedule_data_source_check;
ALTER TABLE student_academic_schedule ADD CONSTRAINT student_academic_schedule_data_source_check CHECK(data_source IN ('TEST','MANUAL'));
ALTER TABLE student_score ADD COLUMN version integer NOT NULL DEFAULT 1 CHECK(version>0);
CREATE TABLE business_audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 actor_id bigint REFERENCES sys_user(id) ON DELETE SET NULL,
 object_kind text NOT NULL, object_id text NOT NULL, action text NOT NULL,
 before_data jsonb, after_data jsonb,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_business_audit_object ON business_audit(object_kind,object_id,created_at);
