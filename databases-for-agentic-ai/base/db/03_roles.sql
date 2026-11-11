-- Database identities. Passwords come from Secrets Manager (filled in by seed.py).
-- Deliberately NO object privileges here: each mission grants what its component needs.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'trail_desk_app') THEN CREATE ROLE trail_desk_app LOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bedrock_kb_user') THEN CREATE ROLE bedrock_kb_user LOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'diag_readonly') THEN CREATE ROLE diag_readonly LOGIN; END IF;
END $$;
ALTER ROLE trail_desk_app  PASSWORD '{{APP_PASSWORD}}';
ALTER ROLE bedrock_kb_user PASSWORD '{{KB_PASSWORD}}';
ALTER ROLE diag_readonly   PASSWORD '{{DIAG_PASSWORD}}';
ALTER ROLE trail_desk_app  SET statement_timeout = '5s';
ALTER ROLE diag_readonly   SET statement_timeout = '5s';
GRANT CONNECT ON DATABASE riverbend TO trail_desk_app, bedrock_kb_user, diag_readonly;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
