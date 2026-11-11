variable "region" {
  description = "Region with Bedrock AgentCore (e.g. us-west-2, us-east-1)"
  type        = string
  default     = "us-west-2"
}

variable "model_id" {
  description = "Bedrock cross-region inference profile the agent uses"
  type        = string
  default     = "us.amazon.nova-lite-v1:0"
}

variable "availability_zone_ids" {
  description = "Two AZ ids where AgentCore Runtime supports VPC mode in your region (us-west-2: usw2-az1/az2/az3; us-east-1: use1-az1/az2/az4)"
  type        = list(string)
  default     = ["usw2-az1", "usw2-az2"]
}
