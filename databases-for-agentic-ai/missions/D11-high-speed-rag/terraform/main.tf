# Mission D11 - "Fast RAG that isn't fast"
# A latency-optimised retrieval tool, following AWS's high-speed RAG guidance: Titan V2 at 512
# dimensions, HNSW on Aurora pgvector, and a DynamoDB cache for query embeddings.

locals {
  p  = "riverbend-d11"
  db = data.terraform_remote_state.base.outputs
}

resource "aws_dynamodb_table" "embedding_cache" {
  name         = "${local.p}-embedding-cache"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "cache_key"
  attribute {
    name = "cache_key"
    type = "S"
  }
  ttl {
    enabled        = true
    attribute_name = "expires_at"
  }
}

module "fast_answer" {
  source              = "../../../common/terraform/sql_tool_lambda"
  name                = "${local.p}-fast-answer"
  source_dir          = "${path.module}/../lambdas"
  build_dir           = "${path.module}/build"
  handler             = "fast_answer.handler"
  cluster_arn         = local.db.cluster_arn
  database            = local.db.database
  db_secret_arn       = local.db.app_secret_arn
  allowed_secret_arns = [local.db.app_secret_arn]
  memory_size         = 1024
  environment = {
    EMBED_DIMENSIONS = "512" # Titan V2 at 512-d keeps ~99% of the retrieval accuracy of 1024-d (AWS guidance)
    CACHE_TABLE      = aws_dynamodb_table.embedding_cache.name
  }
  extra_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = "bedrock:InvokeModel", Resource = "arn:aws:bedrock:${var.region}::foundation-model/amazon.titan-embed-text-v2:0" },
      { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem"], Resource = aws_dynamodb_table.embedding_cache.arn },
    ]
  })
}
