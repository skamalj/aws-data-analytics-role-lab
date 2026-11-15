# Registers an S3 prefix with Lake Formation using a dedicated role, so Lake Formation vends credentials for it.
variable "name" { type = string }
variable "bucket" { type = string }
variable "prefix" { type = string } # e.g. "governed/c5/"

resource "aws_iam_role" "this" {
  name_prefix = "${var.name}-lf-"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "lakeformation.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "this" {
  name = "location"
  role = aws_iam_role.this.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = "arn:aws:s3:::${var.bucket}/${var.prefix}*" },
      { Effect = "Allow", Action = ["s3:ListBucket"], Resource = "arn:aws:s3:::${var.bucket}", Condition = { StringLike = { "s3:prefix" = ["${var.prefix}*"] } } },
    ]
  })
}

resource "aws_lakeformation_resource" "this" {
  arn      = "arn:aws:s3:::${var.bucket}/${trimsuffix(var.prefix, "/")}"
  role_arn = aws_iam_role.this.arn
  # LF assumes the role on first use; make sure its policy exists first.
  depends_on = [aws_iam_role_policy.this]
}

output "location" { value = "s3://${var.bucket}/${var.prefix}" }
