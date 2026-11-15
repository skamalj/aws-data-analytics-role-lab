# Mission D14 - "How do customers feel about this product?"
# Aurora machine learning lets SQL call Amazon Comprehend. The cluster needs an IAM role,
# associated for the Comprehend feature, that may call the sentiment APIs.

locals {
  p  = "riverbend-d14"
  db = data.terraform_remote_state.base.outputs
}

data "aws_iam_policy_document" "rds_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["rds.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "aurora_ml" {
  name_prefix        = "${local.p}-aurora-ml-"
  assume_role_policy = data.aws_iam_policy_document.rds_trust.json
}

resource "aws_iam_role_policy" "comprehend" {
  name = "comprehend"
  role = aws_iam_role.aurora_ml.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["comprehend:DetectDominantLanguage"], Resource = "*" }]
  })
}

resource "aws_rds_cluster_role_association" "comprehend" {
  db_cluster_identifier = local.db.cluster_id
  feature_name          = "SageMaker"
  role_arn              = aws_iam_role.aurora_ml.arn
}

module "review_insights" {
  source              = "../../../common/terraform/sql_tool_lambda"
  name                = "${local.p}-review-insights"
  source_dir          = "${path.module}/../lambdas"
  build_dir           = "${path.module}/build"
  handler             = "review_insights.handler"
  cluster_arn         = local.db.cluster_arn
  database            = local.db.database
  db_secret_arn       = local.db.app_secret_arn
  allowed_secret_arns = [local.db.app_secret_arn]
  timeout             = 60
}
