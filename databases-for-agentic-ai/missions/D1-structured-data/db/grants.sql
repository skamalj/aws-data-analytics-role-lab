-- Privileges for trail_desk_app, the identity the agent's order tools use.
-- Applied by missions/D1-structured-data/setup.py (re-runnable).
REVOKE ALL ON ALL TABLES IN SCHEMA commerce FROM trail_desk_app;
REVOKE ALL ON ALL TABLES IN SCHEMA reporting FROM trail_desk_app;

GRANT USAGE ON SCHEMA commerce TO trail_desk_app;
