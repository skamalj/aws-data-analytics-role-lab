-- Spark SQL run by the maintenance job (scenarios/run_maintenance.py). Tables: glue_catalog.riverbend_lakehouse.<table>
SELECT count(*) FROM glue_catalog.riverbend_lakehouse.sales;
