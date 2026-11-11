# Mission D2 - "Manuals in, nothing out"
# Product manuals in S3 are embedded by a Bedrock Knowledge Base into Aurora PostgreSQL (pgvector),
# next to the operational data, and Trail Desk searches them with its search_manuals tool.

locals {
  p     = "riverbend-d2"
  fm_id = replace(var.model_id, "/^(us|eu|apac|global)\\./", "")
  db    = data.terraform_remote_state.base.outputs
}

module "base" {
  source      = "../../../common/terraform/agent_base"
  name_prefix = local.p
  zip_path    = "${path.module}/build/agent.zip"
}

resource "aws_s3_bucket" "docs" {
  bucket_prefix = "${local.p}-docs-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "docs" {
  bucket                  = aws_s3_bucket.docs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "docs" {
  for_each     = fileset("${path.module}/../docs", "*.md")
  bucket       = aws_s3_bucket.docs.id
  key          = "manuals/${each.value}"
  source       = "${path.module}/../docs/${each.value}"
  etag         = filemd5("${path.module}/../docs/${each.value}")
  content_type = "text/markdown"
}

# ----------------------------------------------------------------- knowledge base on Aurora
data "aws_iam_policy_document" "kb_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [module.base.account_id]
    }
  }
}

resource "aws_iam_role" "kb" {
  name_prefix        = "${local.p}-kb-"
  assume_role_policy = data.aws_iam_policy_document.kb_trust.json
}

data "aws_iam_policy_document" "kb" {
  statement {
    sid       = "Embed"
    actions   = ["bedrock:InvokeModel"]
    resources = ["arn:aws:bedrock:${var.region}::foundation-model/${var.embedding_model_id}"]
  }
  statement {
    sid       = "ReadDocs"
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [aws_s3_bucket.docs.arn, "${aws_s3_bucket.docs.arn}/*"]
  }
  statement {
    sid       = "Cluster"
    actions   = ["rds:DescribeDBClusters"]
    resources = [local.db.cluster_arn]
  }
  statement {
    sid       = "DataApi"
    actions   = ["rds-data:ExecuteStatement", "rds-data:BatchExecuteStatement"]
    resources = [local.db.cluster_arn]
  }
}

resource "aws_iam_role_policy" "kb" {
  name   = "kb-access"
  role   = aws_iam_role.kb.id
  policy = data.aws_iam_policy_document.kb.json
}

resource "aws_bedrockagent_knowledge_base" "manuals" {
  name     = "${local.p}-manuals"
  role_arn = aws_iam_role.kb.arn

  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${var.region}::foundation-model/${var.embedding_model_id}"
      embedding_model_configuration {
        bedrock_embedding_model_configuration {
          dimensions          = 1024
          embedding_data_type = "FLOAT32"
        }
      }
    }
  }

  storage_configuration {
    type = "RDS"
    rds_configuration {
      resource_arn           = local.db.cluster_arn
      credentials_secret_arn = local.db.kb_secret_arn
      database_name          = local.db.database
      table_name             = "bedrock_kb.manual_chunks"
      field_mapping {
        primary_key_field     = "id"
        vector_field          = "embedding"
        text_field            = "chunks"
        metadata_field        = "metadata"
        custom_metadata_field = "custom_metadata"
      }
    }
  }

  depends_on = [aws_iam_role_policy.kb]
}

resource "aws_bedrockagent_data_source" "manuals" {
  name              = "product-manuals"
  knowledge_base_id = aws_bedrockagent_knowledge_base.manuals.id

  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn         = aws_s3_bucket.docs.arn
      inclusion_prefixes = ["manuals/"]
    }
  }

  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = "FIXED_SIZE"
      fixed_size_chunking_configuration {
        max_tokens         = 300
        overlap_percentage = 15
      }
    }
  }
}

# ----------------------------------------------------------------- agent
data "aws_iam_policy_document" "agent" {
  statement {
    sid     = "InvokeModel"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [
      "arn:aws:bedrock:${var.region}:${module.base.account_id}:inference-profile/${var.model_id}",
      "arn:aws:bedrock:*::foundation-model/${local.fm_id}",
    ]
  }
  statement {
    sid       = "SearchManuals"
    actions   = ["bedrock:Retrieve"]
    resources = [aws_bedrockagent_knowledge_base.manuals.arn]
  }
}

resource "aws_iam_role_policy" "agent" {
  name   = "agent-access"
  role   = module.base.role_name
  policy = data.aws_iam_policy_document.agent.json
}

resource "aws_bedrockagentcore_agent_runtime" "trail_desk" {
  agent_runtime_name = "riverbend_d2_trail_desk"
  description        = "Trail Desk with manuals on pgvector (mission D2)"
  role_arn           = module.base.role_arn

  agent_runtime_artifact {
    code_configuration {
      entry_point = ["agent.py"]
      runtime     = "PYTHON_3_12"
      code {
        s3 {
          bucket     = module.base.bucket
          prefix     = module.base.key
          version_id = module.base.version_id
        }
      }
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  environment_variables = {
    MODEL_ID = var.model_id
    KB_ID    = aws_bedrockagent_knowledge_base.manuals.id
  }

  depends_on = [aws_iam_role_policy.agent]
}
