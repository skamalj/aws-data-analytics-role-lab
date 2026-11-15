variable "region" {
  description = "Region for every AWS resource (needs Bedrock Titan Text Embeddings V2 + Nova Pro, OpenSearch Serverless, Aurora Serverless v2)"
  type        = string
  default     = "us-east-1"
}

variable "prefix" {
  description = "Name prefix for all resources"
  type        = string
  default     = "gmlab"
}

variable "my_ip_cidr" {
  description = "Your laptop's public IP as a /32 (e.g. 203.0.113.7/32). Only this address can reach Aurora on 5432. Find it with: curl -s https://checkip.amazonaws.com"
  type        = string
}

variable "create_aurora" {
  description = "Create the Aurora PostgreSQL (pgvector) cluster. Set false to use a local PostgreSQL with pgvector instead."
  type        = bool
  default     = true
}

variable "aurora_engine_version" {
  description = "Aurora PostgreSQL version. 16.6 ships pgvector 0.8.0 (HNSW needs >= 0.5.0) and supports Serverless v2 auto-pause (min 0 ACU)."
  type        = string
  default     = "16.6"
}
