output "runtime_arn" { value = aws_bedrockagentcore_agent_runtime.reporting.agent_runtime_arn }
output "legacy_batch_role_arn" { value = aws_iam_role.legacy_batch.arn }
output "clients" {
  sensitive = true
  value = {
    compliance_portal = { id = aws_cognito_user_pool_client.compliance_portal.id, secret = aws_cognito_user_pool_client.compliance_portal.client_secret }
    advisor_portal    = { id = aws_cognito_user_pool_client.advisor_portal.id, secret = aws_cognito_user_pool_client.advisor_portal.client_secret }
  }
}
