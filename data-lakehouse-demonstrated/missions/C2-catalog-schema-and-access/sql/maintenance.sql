-- Spark SQL run by the maintenance job (scenarios/run_maintenance.py uploads this file and runs it).
-- Tables: glue_catalog.riverbend_lakehouse.<table>
SELECT count(*) FROM glue_catalog.riverbend_lakehouse.products;
