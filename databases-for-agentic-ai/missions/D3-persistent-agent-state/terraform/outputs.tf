output "runtime_arn" { value = aws_bedrockagentcore_agent_runtime.trail_desk.agent_runtime_arn }
output "auth_mode" { value = "iam" }
output "checkpoint_table" { value = aws_dynamodb_table.checkpoints.name }
output "runtime_role_name" { value = module.base.role_name }
output "log_group_hint" { value = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.trail_desk.agent_runtime_id}-DEFAULT" }
