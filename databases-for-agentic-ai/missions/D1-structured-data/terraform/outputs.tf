output "runtime_arn" { value = aws_bedrockagentcore_agent_runtime.trail_desk.agent_runtime_arn }
output "auth_mode" { value = "iam" }
output "tools_function" { value = aws_lambda_function.tools.function_name }
output "gateway_id" { value = aws_bedrockagentcore_gateway.tools.gateway_id }
output "log_group_hint" { value = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.trail_desk.agent_runtime_id}-DEFAULT" }
