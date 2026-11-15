variable "region" {
  type    = string
  default = "us-west-2"
}

variable "model_id" {
  description = "Bedrock cross-region inference profile used by the agent"
  type        = string
  default     = "us.amazon.nova-lite-v1:0"
}
