-- Read-only identity prepared by the platform team for diagnostics tooling (applied by setup.py).
GRANT USAGE ON SCHEMA commerce, reporting, bedrock_kb TO diag_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA commerce, reporting, bedrock_kb TO diag_readonly;
ALTER ROLE diag_readonly SET default_transaction_read_only = on;
