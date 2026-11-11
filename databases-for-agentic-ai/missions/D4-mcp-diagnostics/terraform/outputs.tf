output "runtime_arn" { value = aws_bedrockagentcore_agent_runtime.diagnostics.agent_runtime_arn }
output "runtime_id" { value = aws_bedrockagentcore_agent_runtime.diagnostics.agent_runtime_id }
output "runtime_role_arn" { value = module.base.role_arn }
output "sessions_table" { value = aws_dynamodb_table.sessions.name }
output "log_group_hint" { value = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.diagnostics.agent_runtime_id}-DEFAULT" }
