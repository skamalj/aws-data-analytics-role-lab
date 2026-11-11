variable "region" {
  type    = string
  default = "us-west-2"
}

variable "model_id" {
  description = "Bedrock cross-region inference profile used by the agent"
  type        = string
  default     = "us.amazon.nova-lite-v1:0"
}

variable "embedding_model_id" {
  type    = string
  default = "amazon.titan-embed-text-v2:0"
}
