# Shared foundation for missions D1, D2, D4 and D5:
# Aurora PostgreSQL Serverless v2 (Data API on, pgvector available) in a private VPC,
# plus three least-privilege database identities whose credentials live in Secrets Manager.
# The schema, data and roles are created by base/seed.py (run by ./scripts/deploy.sh base).

data "aws_caller_identity" "me" {}

locals {
  p = "riverbend-db"
}

resource "aws_vpc" "db" {
  cidr_block           = "10.30.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${local.p}-vpc" }
}

data "aws_availability_zones" "az" {
  state = "available"
}

resource "aws_subnet" "db" {
  count             = 2
  vpc_id            = aws_vpc.db.id
  cidr_block        = cidrsubnet("10.30.0.0/16", 8, count.index + 1)
  availability_zone = data.aws_availability_zones.az.names[count.index]
  tags              = { Name = "${local.p}-private-${count.index + 1}" }
}

resource "aws_db_subnet_group" "db" {
  name       = "${local.p}-subnets"
  subnet_ids = aws_subnet.db[*].id
}

resource "aws_security_group" "db" {
  name_prefix = "${local.p}-aurora-"
  description = "Aurora: no inbound rules - all access goes through the RDS Data API"
  vpc_id      = aws_vpc.db.id
}

resource "aws_rds_cluster" "shop" {
  cluster_identifier          = "${local.p}-shop"
  engine                      = "aurora-postgresql"
  engine_mode                 = "provisioned"
  engine_version              = var.engine_version
  database_name               = "riverbend"
  master_username             = "dbadmin"
  manage_master_user_password = true
  enable_http_endpoint        = true # RDS Data API: used by Lambda tools, Bedrock KB, MCP server and seed scripts
  db_subnet_group_name        = aws_db_subnet_group.db.name
  vpc_security_group_ids      = [aws_security_group.db.id]
  storage_encrypted           = true
  skip_final_snapshot         = true
  deletion_protection         = false
  backup_retention_period     = 1

  serverlessv2_scaling_configuration {
    min_capacity             = var.min_acu
    max_capacity             = 4
    seconds_until_auto_pause = var.min_acu == 0 ? 900 : null
  }
}

resource "aws_rds_cluster_instance" "writer" {
  identifier         = "${local.p}-shop-1"
  cluster_identifier = aws_rds_cluster.shop.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.shop.engine
  engine_version     = aws_rds_cluster.shop.engine_version
}

# ----------------------------------------------------------------- database identities
locals {
  identities = {
    app  = { username = "trail_desk_app", purpose = "Agent tools: read curated order data" }
    kb   = { username = "bedrock_kb_user", purpose = "Bedrock Knowledge Base: manage the vector table" }
    diag = { username = "diag_readonly", purpose = "Developer diagnostics (MCP): read-only inspection" }
  }
}

resource "random_password" "db" {
  for_each         = local.identities
  length           = 24
  special          = true
  override_special = "-_=+!#"
}

resource "aws_secretsmanager_secret" "db" {
  for_each                = local.identities
  name_prefix             = "${local.p}-${each.key}-"
  description             = each.value.purpose
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "db" {
  for_each  = local.identities
  secret_id = aws_secretsmanager_secret.db[each.key].id
  secret_string = jsonencode({
    username = each.value.username
    password = random_password.db[each.key].result
    engine   = "postgres"
    host     = aws_rds_cluster.shop.endpoint
    port     = 5432
    dbname   = "riverbend"
  })
}
