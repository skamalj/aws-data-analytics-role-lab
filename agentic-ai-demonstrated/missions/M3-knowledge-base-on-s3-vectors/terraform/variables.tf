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

variable "embedding_model_id" {
  description = "Embedding model used by the knowledge base"
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}
