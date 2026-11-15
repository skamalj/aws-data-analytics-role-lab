# AWS side of the Graph Memory Agent lab. Your laptop runs the code (notebooks + src/) with your AWS credentials.
#
#   DynamoDB      claims-sessions                  conversational memory (Agent A)          goal 1
#   IAM           <prefix>-McpVectorRole           vector agent role WITH the memory leak   goal 2
#   OpenSearch    Serverless VECTORSEARCH collection: chunk vectors + BM25                   goals 3, 4
#   Aurora        PostgreSQL Serverless v2 + pgvector: vector store B + metric source         goals 3, 4
#   S3            evidence bucket                  graded artifacts                         all goals
#   Bedrock       (account-level model access)     Titan Text Embeddings V2, Nova Pro
#
# Neo4j is not here: run it locally (Neo4j Desktop, a package install, or your own container).
data "aws_caller_identity" "me" {}
data "aws_partition" "p" {}

# The ARN to grant OpenSearch data access to: your role, not the temporary session.
data "aws_iam_session_context" "me" {
  arn = data.aws_caller_identity.me.arn
}

locals {
  account     = data.aws_caller_identity.me.account_id
  learner_arn = data.aws_iam_session_context.me.issuer_arn
  collection  = "${var.prefix}-coa-chunks"
}

# ----------------------------------------------------------------- DynamoDB: conversational memory
resource "aws_dynamodb_table" "sessions" {
  name         = "claims-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"
  range_key    = "turn_id"

  attribute {
    name = "session_id"
    type = "S"
  }
  attribute {
    name = "turn_id"
    type = "N"
  }
}

# ----------------------------------------------------------------- S3: evidence
resource "aws_s3_bucket" "evidence" {
  bucket_prefix = "${var.prefix}-evidence-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "evidence" {
  bucket                  = aws_s3_bucket.evidence.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ----------------------------------------------------------------- IAM: the vector agent's role (goal 2 starts broken)
resource "aws_iam_role" "mcp_vector" {
  name = "${var.prefix}-McpVectorRole"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { AWS = "arn:${data.aws_partition.p.partition}:iam::${local.account}:root" }
    }]
  })
}

# The role's legitimate policy: OpenSearch access plus the lab's deny rules. Leave this one alone.
resource "aws_iam_role_policy" "vector_store" {
  name = "vector-store-access"
  role = aws_iam_role.mcp_vector.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "OpenSearchServerless"
        Effect   = "Allow"
        Action   = ["aoss:APIAccessAll"]
        Resource = aws_opensearchserverless_collection.chunks.arn
      },
      {
        Sid      = "DenyMemoryWrites"
        Effect   = "Deny"
        Action   = ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:BatchWriteItem", "dynamodb:Scan"]
        Resource = "*"
      },
      {
        Sid      = "DenyIdentityChanges"
        Effect   = "Deny"
        Action   = ["iam:*", "sts:AssumeRole"]
        Resource = "*"
      },
    ]
  })
}

# DEFECT (goal 2): an over-broad grant that lets the vector agent read Agent A's private session memory.
# Fix it the way the lab asks - delete this inline policy in the IAM console (or CLI) - not by editing Terraform.
# Note: a later `terraform apply` recreates it; that is how you reset goal 2.
resource "aws_iam_role_policy" "memory_leak" {
  name = "vector-memory-leak"
  role = aws_iam_role.mcp_vector.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "VectorStoreAccess"
      Effect   = "Allow"
      Action   = ["dynamodb:GetItem", "dynamodb:Query"]
      Resource = aws_dynamodb_table.sessions.arn
    }]
  })
}

# ----------------------------------------------------------------- OpenSearch Serverless (vector store A)
resource "aws_opensearchserverless_security_policy" "encryption" {
  name = "${var.prefix}-enc"
  type = "encryption"
  policy = jsonencode({
    Rules       = [{ ResourceType = "collection", Resource = ["collection/${local.collection}"] }]
    AWSOwnedKey = true
  })
}

# Public endpoint so your laptop can reach it; every request is still SigV4-signed and checked against the data access policy.
resource "aws_opensearchserverless_security_policy" "network" {
  name = "${var.prefix}-net"
  type = "network"
  policy = jsonencode([{
    Rules = [
      { ResourceType = "collection", Resource = ["collection/${local.collection}"] },
      { ResourceType = "dashboard", Resource = ["collection/${local.collection}"] },
    ]
    AllowFromPublic = true
  }])
}

resource "aws_opensearchserverless_access_policy" "data" {
  name = "${var.prefix}-data"
  type = "data"
  policy = jsonencode([{
    Rules = [
      { ResourceType = "collection", Resource = ["collection/${local.collection}"], Permission = ["aoss:*"] },
      { ResourceType = "index", Resource = ["index/${local.collection}/*"], Permission = ["aoss:*"] },
    ]
    Principal = [local.learner_arn, aws_iam_role.mcp_vector.arn]
  }])
}

resource "aws_opensearchserverless_collection" "chunks" {
  name             = local.collection
  type             = "VECTORSEARCH"
  standby_replicas = "DISABLED" # dev/test: halves the minimum OCUs
  depends_on       = [aws_opensearchserverless_security_policy.encryption, aws_opensearchserverless_security_policy.network]
}

# ----------------------------------------------------------------- Aurora PostgreSQL Serverless v2 + pgvector (vector store B)
data "aws_vpc" "default" {
  count   = var.create_aurora ? 1 : 0
  default = true
}

data "aws_subnets" "default" {
  count = var.create_aurora ? 1 : 0
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default[0].id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

resource "random_password" "pg" {
  count   = var.create_aurora ? 1 : 0
  length  = 24
  special = false
}

resource "aws_db_subnet_group" "pg" {
  count      = var.create_aurora ? 1 : 0
  name       = "${var.prefix}-pg"
  subnet_ids = data.aws_subnets.default[0].ids
}

resource "aws_security_group" "pg" {
  count       = var.create_aurora ? 1 : 0
  name_prefix = "${var.prefix}-pg-"
  description = "Aurora PostgreSQL: reachable only from the learner's laptop"
  vpc_id      = data.aws_vpc.default[0].id
  ingress {
    description = "PostgreSQL from my laptop"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_rds_cluster" "pg" {
  count                  = var.create_aurora ? 1 : 0
  cluster_identifier     = "${var.prefix}-coa"
  engine                 = "aurora-postgresql"
  engine_mode            = "provisioned"
  engine_version         = var.aurora_engine_version
  database_name          = "coa"
  master_username        = "coaadmin"
  master_password        = random_password.pg[0].result
  db_subnet_group_name   = aws_db_subnet_group.pg[0].name
  vpc_security_group_ids = [aws_security_group.pg[0].id]
  storage_encrypted      = true
  skip_final_snapshot    = true
  apply_immediately      = true

  serverlessv2_scaling_configuration {
    min_capacity             = 0 # auto-pause when idle; the first query after a pause takes ~15-30 s
    max_capacity             = 2
    seconds_until_auto_pause = 1800
  }
}

resource "aws_rds_cluster_instance" "pg" {
  count               = var.create_aurora ? 1 : 0
  identifier          = "${var.prefix}-coa-1"
  cluster_identifier  = aws_rds_cluster.pg[0].id
  instance_class      = "db.serverless"
  engine              = aws_rds_cluster.pg[0].engine
  engine_version      = aws_rds_cluster.pg[0].engine_version
  publicly_accessible = true # in a default-VPC public subnet, locked to my_ip_cidr by the security group
}
