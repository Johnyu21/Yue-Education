-- M5 additive schema; apply after deploy/schema.sql. No ALTER/DROP.

CREATE TABLE IF NOT EXISTS m5_daily (
	id VARCHAR NOT NULL, 
	user_id BIGINT NOT NULL, 
	dept_id BIGINT NOT NULL, 
	report_date VARCHAR NOT NULL, 
	original_text TEXT NOT NULL, 
	content JSON NOT NULL, 
	status VARCHAR NOT NULL, 
	return_reason TEXT NOT NULL, 
	version INTEGER NOT NULL, 
	approved_snapshot JSON, 
	submitted_at VARCHAR, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_m5_daily_user_date UNIQUE (user_id, report_date), 
	CONSTRAINT ck_m5_daily_status CHECK (status IN ('DRAFT','SUBMITTED','APPROVED','RETURNED')), 
	FOREIGN KEY(user_id) REFERENCES sys_user (id), 
	FOREIGN KEY(dept_id) REFERENCES sys_department (id)
)

;
CREATE INDEX IF NOT EXISTS ix_m5_daily_dept_date ON m5_daily (dept_id, report_date);

CREATE TABLE IF NOT EXISTS m5_report (
	id VARCHAR NOT NULL, 
	owner_id BIGINT NOT NULL, 
	dept_id BIGINT NOT NULL, 
	kind VARCHAR NOT NULL, 
	scope_employee_ids JSON NOT NULL, 
	scope_student_ids JSON NOT NULL, 
	title VARCHAR NOT NULL, 
	start_date VARCHAR NOT NULL, 
	end_date VARCHAR NOT NULL, 
	narrative TEXT NOT NULL, 
	metrics JSON NOT NULL, 
	scope VARCHAR NOT NULL, 
	ai_status VARCHAR NOT NULL, 
	warnings JSON NOT NULL, 
	status VARCHAR NOT NULL, 
	version INTEGER NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_m5_report_status CHECK (status IN ('DRAFT','SUBMITTED')), 
	FOREIGN KEY(owner_id) REFERENCES sys_user (id), 
	FOREIGN KEY(dept_id) REFERENCES sys_department (id)
)

;
CREATE INDEX IF NOT EXISTS ix_m5_report_dept_owner ON m5_report (dept_id, owner_id);

CREATE TABLE IF NOT EXISTS m5_chat (
	user_id BIGINT NOT NULL, 
	messages JSON NOT NULL, 
	draft JSON NOT NULL, 
	last_key VARCHAR NOT NULL, 
	last_result JSON NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(user_id) REFERENCES sys_user (id)
)

;
