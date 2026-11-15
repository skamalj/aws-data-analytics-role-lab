# Mission D12 - "Tenants see each other"
# One table for all tenants, isolated by PostgreSQL row-level security (self-managed multi-tenant
# vector search on Aurora). The SaaS service has its own database identity, saas_app.

locals {
  p  = "riverbend-d12"
  db = data.terraform_remote_state.base.outputs
}

resource "random_password" "saas" {
  length           = 24
  special          = true
  override_special = "-_=+!#"
}

resource "aws_secretsmanager_secret" "saas" {
  name_prefix             = "${local.p}-saas-app-"
  description             = "Database identity of the multi-tenant document service"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "saas" {
  secret_id     = aws_secretsmanager_secret.saas.id
  secret_string = jsonencode({ username = "saas_app", password = random_password.saas.result, engine = "postgres", dbname = "riverbend" })
}

module "tenant_search" {
  source              = "../../../common/terraform/sql_tool_lambda"
  name                = "${local.p}-tenant-search"
  source_dir          = "${path.module}/../lambdas"
  build_dir           = "${path.module}/build"
  handler             = "tenant_search.handler"
  cluster_arn         = local.db.cluster_arn
  database            = local.db.database
  db_secret_arn       = aws_secretsmanager_secret.saas.arn
  allowed_secret_arns = [aws_secretsmanager_secret.saas.arn]
}
