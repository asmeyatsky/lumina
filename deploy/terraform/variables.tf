# =============================================================================
# LUMINA — Terraform Variables
# =============================================================================

# --- Project -----------------------------------------------------------------

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "project_name" {
  description = "Project name used as prefix for resources"
  type        = string
  default     = "lumina"
}

variable "region" {
  description = "GCP region for all resources"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment (staging or production)"
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be 'staging' or 'production'."
  }
}

# --- Domain ------------------------------------------------------------------

variable "domain_name" {
  description = "Custom domain name (leave empty to skip load balancer setup)"
  type        = string
  default     = ""
}

# --- Database ----------------------------------------------------------------

variable "db_tier" {
  description = "Cloud SQL machine tier"
  type        = string
  default     = "db-custom-2-4096"
}

variable "db_disk_size" {
  description = "Cloud SQL disk size in GB"
  type        = number
  default     = 20
}

# --- GitHub ------------------------------------------------------------------

variable "github_repo" {
  description = "GitHub repository in 'owner/repo' format for Workload Identity Federation"
  type        = string
  default     = ""
}

# --- API Keys (passed via tfvars or env) -------------------------------------

variable "anthropic_api_key" {
  description = "Anthropic API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "google_ai_api_key" {
  description = "Google AI (Gemini) API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "perplexity_api_key" {
  description = "Perplexity API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "neo4j_uri" {
  description = "Neo4j connection URI"
  type        = string
  sensitive   = true
  default     = ""
}

variable "neo4j_password" {
  description = "Neo4j password"
  type        = string
  sensitive   = true
  default     = ""
}

variable "pinecone_api_key" {
  description = "Pinecone API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "redis_url" {
  description = "Redis connection URL"
  type        = string
  sensitive   = true
  default     = ""
}

variable "sendgrid_api_key" {
  description = "SendGrid API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for notifications"
  type        = string
  sensitive   = true
  default     = ""
}
