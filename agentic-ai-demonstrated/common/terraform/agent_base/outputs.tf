output "role_arn" { value = aws_iam_role.runtime.arn }
output "role_name" { value = aws_iam_role.runtime.name }
output "bucket" { value = aws_s3_bucket.artifacts.id }
output "key" { value = aws_s3_object.agent_zip.key }
output "version_id" { value = aws_s3_object.agent_zip.version_id }
output "account_id" { value = local.account }
output "region" { value = local.region }
