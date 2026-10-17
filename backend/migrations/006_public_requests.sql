CREATE TABLE public_request (
 operation varchar(80) NOT NULL, request_key uuid NOT NULL, fingerprint varchar(64) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(operation,request_key)
);
