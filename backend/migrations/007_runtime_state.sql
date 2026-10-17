CREATE TABLE runtime_state (
 key varchar(200) PRIMARY KEY, value jsonb NOT NULL, expires_at timestamptz NOT NULL
);
CREATE INDEX ix_runtime_state_expiry ON runtime_state(expires_at);
CREATE TABLE runtime_rate (
 key varchar(64) PRIMARY KEY,tokens double precision NOT NULL, updated_at timestamptz NOT NULL
);
CREATE INDEX ix_runtime_rate_expiry ON runtime_rate(updated_at);
