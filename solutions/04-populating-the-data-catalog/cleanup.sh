#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
try aws glue delete-crawler --name cq-da-04-landing-crawler
try aws glue delete-classifier --name cq-da-04-pos-psv
try aws glue delete-database --name riverbend_catalog
echo "Lab 04 resources removed. Now run ./scripts/destroy.sh 04-populating-the-data-catalog"
