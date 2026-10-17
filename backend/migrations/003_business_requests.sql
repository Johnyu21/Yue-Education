CREATE TABLE business_request (
 actor_id bigint NOT NULL REFERENCES sys_user(id) ON DELETE CASCADE,
 operation varchar(100) NOT NULL,
 request_key uuid NOT NULL,
 fingerprint varchar(64) NOT NULL,
 response jsonb,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(actor_id, operation, request_key)
);
CREATE INDEX ix_business_request_created ON business_request(created_at);
