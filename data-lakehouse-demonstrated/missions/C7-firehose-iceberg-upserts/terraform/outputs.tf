output "stream_name" { value = aws_kinesis_firehose_delivery_stream.orders.name }
output "error_prefix" { value = local.error_pref }
output "log_group" { value = aws_cloudwatch_log_group.firehose.name }
