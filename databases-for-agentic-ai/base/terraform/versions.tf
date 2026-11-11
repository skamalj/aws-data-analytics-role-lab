terraform {
  required_version = ">= 1.6"
  required_providers {
    aws    = { source = "hashicorp/aws", version = ">= 6.72.0" }
    random = { source = "hashicorp/random", version = ">= 3.6.0" }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "riverbend-db-agentic-labs", Mission = "base" }
  }
}
