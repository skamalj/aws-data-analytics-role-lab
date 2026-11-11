output "runtime_arn" { value = aws_bedrockagentcore_agent_runtime.trail_desk.agent_runtime_arn }
output "auth_mode" { value = "iam" }
output "guardrail_id" { value = aws_bedrock_guardrail.trail_desk.guardrail_id }
output "guardrail_version_in_use" { value = aws_bedrock_guardrail_version.v1.version }
output "runtime_role_name" { value = module.base.role_name }
output "log_group_hint" { value = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.trail_desk.agent_runtime_id}-DEFAULT" }
