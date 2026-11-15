output "region" { value = var.region }
output "account_id" { value = local.account }
output "session_table" { value = aws_dynamodb_table.sessions.name }
output "session_table_arn" { value = aws_dynamodb_table.sessions.arn }
output "evidence_bucket" { value = aws_s3_bucket.evidence.id }
output "mcp_vector_role_name" { value = aws_iam_role.mcp_vector.name }
output "mcp_vector_role_arn" { value = aws_iam_role.mcp_vector.arn }
output "opensearch_endpoint" { value = aws_opensearchserverless_collection.chunks.collection_endpoint }
output "pg_host" { value = var.create_aurora ? aws_rds_cluster.pg[0].endpoint : "" }
output "pg_password" {
  value     = var.create_aurora ? random_password.pg[0].result : ""
  sensitive = true
}
