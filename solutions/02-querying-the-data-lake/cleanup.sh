#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
try athena cq-da-02 -e "DROP VIEW IF EXISTS riverbend_lake.v_order_details"
try athena cq-da-02 -e "DROP TABLE IF EXISTS riverbend_lake.orders_parquet"
try aws athena delete-work-group --work-group cq-da-02-analysts --recursive-delete-option
echo "Lab 02 resources removed (curated objects are emptied by destroy.sh). Now run ./scripts/destroy.sh 02-querying-the-data-lake"
