# Challenge C4 - analytics dashboards must answer in under 5 seconds
locals {
  b = data.terraform_remote_state.base.outputs
}

module "load_sales" {
  source          = "../../../common/terraform/iceberg_glue_job"
  name            = "riverbend-lh-c4-load-sales"
  script_path     = "${path.module}/../glue/load_sales.py"
  scripts_bucket  = local.b.scripts_bucket
  role_arn        = local.b.glue_role_arn
  warehouse       = local.b.warehouse
  workers         = 4
  timeout_minutes = 30
}

module "maintenance" {
  source          = "../../../common/terraform/iceberg_glue_job"
  name            = "riverbend-lh-c4-maintenance"
  script_path     = "${path.module}/../glue/maintenance.py"
  scripts_bucket  = local.b.scripts_bucket
  role_arn        = local.b.glue_role_arn
  warehouse       = local.b.warehouse
  workers         = 4
  timeout_minutes = 30
}
