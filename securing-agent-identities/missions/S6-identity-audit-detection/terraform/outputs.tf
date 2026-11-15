output "trail_name" { value = aws_cloudtrail.identity.name }
output "log_group" { value = aws_cloudwatch_log_group.trail.name }
output "delivery_role_arn" { value = aws_iam_role.trail_to_logs.arn }
output "namespace" { value = local.namespace }
output "alarms" { value = [aws_cloudwatch_metric_alarm.token_denied.alarm_name, aws_cloudwatch_metric_alarm.identity_tampering.alarm_name] }
output "filters" { value = { token_denied = aws_cloudwatch_log_metric_filter.token_denied.name, tampering = aws_cloudwatch_log_metric_filter.identity_tampering.name } }
output "topic_arn" { value = aws_sns_topic.alerts.arn }
output "canary_name" { value = aws_bedrockagentcore_workload_identity.canary.name }
output "canary_arn" { value = aws_bedrockagentcore_workload_identity.canary.workload_identity_arn }
output "rogue_role_arn" { value = aws_iam_role.rogue.arn }
