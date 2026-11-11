output "runtime_arn" { value = aws_bedrockagentcore_agent_runtime.trail_desk.agent_runtime_arn }
output "auth_mode" { value = "jwt" }
output "token_url" { value = "https://${aws_cognito_user_pool_domain.staff.domain}.auth.${var.region}.amazoncognito.com/oauth2/token" }
output "client_id" { value = aws_cognito_user_pool_client.console.id }
output "client_secret" {
  value     = aws_cognito_user_pool_client.console.client_secret
  sensitive = true
}
output "requested_scope" {
  description = "Scope the web console asks Cognito for"
  value       = local.invoke_scope
}
output "discovery_url" { value = local.discovery }
output "runtime_role_name" { value = module.base.role_name }
output "log_group_hint" { value = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.trail_desk.agent_runtime_id}-DEFAULT" }
