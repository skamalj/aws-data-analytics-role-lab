# Mission 3 - "The manuals are there, but the agent can't find them"
# Product manuals and policies live in S3; a Bedrock Knowledge Base embeds them into an
# Amazon S3 Vectors index; Trail Desk searches it through its search_manuals tool.

locals {
  p     = "riverbend-m3"
  fm_id = replace(var.model_id, "/^(us|eu|apac|global)\\./", "")
  docs  = fileset("${path.module}/../docs", "*.md")
}

module "base" {
  source      = "../../../common/terraform/agent_base"
  name_prefix = local.p
  zip_path    = "${path.module}/build/agent.zip"
}

# ----------------------------------------------------------------- source documents
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
  for_each     = local.docs
  bucket       = aws_s3_bucket.docs.id
  key          = "library/${each.value}"
  source       = "${path.module}/../docs/${each.value}"
  etag         = filemd5("${path.module}/../docs/${each.value}")
  content_type = "text/markdown"
}

# ----------------------------------------------------------------- vector store
resource "aws_s3vectors_vector_bucket" "kb" {
  vector_bucket_name = "${local.p}-vectors-${module.base.account_id}"
  force_destroy      = true
}

resource "aws_s3vectors_index" "manuals" {
  vector_bucket_name = aws_s3vectors_vector_bucket.kb.vector_bucket_name
  index_name         = "manuals"
  data_type          = "float32"
  dimension          = 1024
  distance_metric    = "cosine"
}

# ----------------------------------------------------------------- knowledge base
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
    sid       = "WriteVectors"
    actions   = ["s3vectors:PutVectors", "s3vectors:GetVectors", "s3vectors:DeleteVectors", "s3vectors:QueryVectors", "s3vectors:GetIndex"]
    resources = ["arn:aws:s3vectors:${var.region}:${module.base.account_id}:bucket/${aws_s3vectors_vector_bucket.kb.vector_bucket_name}/index/*"]
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
    type = "S3_VECTORS"
    s3_vectors_configuration {
      index_arn = aws_s3vectors_index.manuals.index_arn
    }
  }

  depends_on = [aws_iam_role_policy.kb]
}

resource "aws_bedrockagent_data_source" "library" {
  name              = "product-library"
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
        max_tokens         = 1000
        overlap_percentage = 10
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
    actions   = ["bedrock:RetrieveAndGenerate"]
    resources = [aws_bedrockagent_knowledge_base.manuals.arn]
  }
}

resource "aws_iam_role_policy" "agent" {
  name   = "agent-access"
  role   = module.base.role_name
  policy = data.aws_iam_policy_document.agent.json
}

resource "aws_bedrockagentcore_agent_runtime" "trail_desk" {
  agent_runtime_name = "riverbend_m3_trail_desk"
  description        = "Trail Desk with product knowledge (mission 3)"
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
