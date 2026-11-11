#!/usr/bin/env bash
# Removes the QuickSight data source/datasets. Delete the analysis and dashboard in the console first.
# Unsubscribing from QuickSight (Manage QuickSight > Account settings) stops its monthly charges.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/common/lib.sh"
aws cloudformation delete-stack --stack-name cq-da-12-solution
aws cloudformation wait stack-delete-complete --stack-name cq-da-12-solution
echo "Lab 12 QuickSight assets removed. Now run ./scripts/destroy.sh 12-business-intelligence-quicksight"
