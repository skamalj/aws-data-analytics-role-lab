# Challenge C1 - order ingestion produces duplicates
locals {
  b = data.terraform_remote_state.base.outputs
}

module "orders_ingest" {
  source           = "../../../common/terraform/iceberg_glue_job"
  name             = "riverbend-lh-c1-orders-ingest"
  script_path      = "${path.module}/../glue/orders_ingest.py"
  scripts_bucket   = local.b.scripts_bucket
  role_arn         = local.b.glue_role_arn
  warehouse        = local.b.warehouse
  datalake_formats = "" # the ETL team: "not needed - the job only reads JSON"
}
