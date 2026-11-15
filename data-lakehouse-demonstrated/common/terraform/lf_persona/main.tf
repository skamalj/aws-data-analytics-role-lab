# A persona role for the governed challenges: Athena in the riverbend-lh workgroup, Glue catalog reads, and
# lakeformation:GetDataAccess. It has NO S3 access to the lake - data access comes only from Lake Formation grants.
variable "name" { type = string }
variable "account_id" { type = string }
variable "region" { type = string }
variable "athena_workgroup" { type = string }
variable "athena_bucket" { type = string }

resource "aws_iam_role" "this" {
  name = var.name
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { AWS = "arn:aws:iam::${var.account_id}:root" } }]
  })
}

resource "aws_iam_role_policy" "this" {
  name = "analyst"
  role = aws_iam_role.this.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults", "athena:StopQueryExecution", "athena:GetWorkGroup"],
      Resource = "arn:aws:athena:${var.region}:${var.account_id}:workgroup/${var.athena_workgroup}" },
      { Effect = "Allow", Action = ["glue:GetDatabase", "glue:GetDatabases", "glue:GetTable", "glue:GetTables", "glue:GetPartition", "glue:GetPartitions", "glue:BatchGetPartition"], Resource = "*" },
      { Effect = "Allow", Action = ["lakeformation:GetDataAccess"], Resource = "*" },
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:GetBucketLocation", "s3:AbortMultipartUpload"],
      Resource = ["arn:aws:s3:::${var.athena_bucket}", "arn:aws:s3:::${var.athena_bucket}/*"] },
    ]
  })
}

output "arn" { value = aws_iam_role.this.arn }
output "name" { value = aws_iam_role.this.name }
