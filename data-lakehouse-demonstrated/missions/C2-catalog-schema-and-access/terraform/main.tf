# Challenge C2 - product catalog schema mismatch and query access patterns
locals {
  b = data.terraform_remote_state.base.outputs
}

module "products_merge" {
  source         = "../../../common/terraform/iceberg_glue_job"
  name           = "riverbend-lh-c2-products-merge"
  script_path    = "${path.module}/../glue/products_merge.py"
  scripts_bucket = local.b.scripts_bucket
  role_arn       = local.b.glue_role_arn
  warehouse      = local.b.warehouse
}

module "maintenance" {
  source         = "../../../common/terraform/iceberg_glue_job"
  name           = "riverbend-lh-c2-maintenance"
  script_path    = "${path.module}/../glue/maintenance.py"
  scripts_bucket = local.b.scripts_bucket
  role_arn       = local.b.glue_role_arn
  warehouse      = local.b.warehouse
}
