output "runtime_arn" { value = aws_bedrockagentcore_agent_runtime.advisor.agent_runtime_arn }
output "staging_token_url" { value = "https://${aws_cognito_user_pool_domain.staging.domain}.auth.${local.b.region}.amazoncognito.com/oauth2/token" }
output "clients" {
  sensitive = true
  value = {
    advisor_portal = { id = aws_cognito_user_pool_client.advisor_portal.id, secret = aws_cognito_user_pool_client.advisor_portal.client_secret }
    analytics      = { id = aws_cognito_user_pool_client.analytics.id, secret = aws_cognito_user_pool_client.analytics.client_secret }
    staging        = { id = aws_cognito_user_pool_client.staging.id, secret = aws_cognito_user_pool_client.staging.client_secret }
  }
}
