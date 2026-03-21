# =============================================================================
# LUMINA — Terraform Outputs
# =============================================================================

# --- Cloud Run URLs ----------------------------------------------------------

output "backend_url" {
  description = "Cloud Run backend service URL"
  value       = google_cloud_run_v2_service.backend.uri
}

output "frontend_url" {
  description = "Cloud Run frontend service URL"
  value       = google_cloud_run_v2_service.frontend.uri
}

# --- Database ----------------------------------------------------------------

output "database_instance_name" {
  description = "Cloud SQL instance name"
  value       = google_sql_database_instance.postgres.name
}

output "database_connection_name" {
  description = "Cloud SQL connection name (project:region:instance)"
  value       = google_sql_database_instance.postgres.connection_name
}

output "database_private_ip" {
  description = "Cloud SQL private IP address"
  value       = google_sql_database_instance.postgres.private_ip_address
  sensitive   = true
}

output "database_url" {
  description = "Full PostgreSQL connection string"
  value       = "postgresql://lumina:${random_password.db_password.result}@${google_sql_database_instance.postgres.private_ip_address}:5432/lumina"
  sensitive   = true
}

# --- Artifact Registry -------------------------------------------------------

output "artifact_registry_url" {
  description = "Artifact Registry repository URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}"
}

# --- Load Balancer -----------------------------------------------------------

output "load_balancer_ip" {
  description = "External IP of the load balancer (if domain configured)"
  value       = var.domain_name != "" ? google_compute_global_forwarding_rule.main[0].ip_address : null
}

output "domain_url" {
  description = "Application URL via custom domain"
  value       = var.domain_name != "" ? "https://${var.domain_name}" : null
}

# --- Workload Identity Federation -------------------------------------------

output "workload_identity_provider" {
  description = "Workload Identity Provider resource name (for GitHub Actions)"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "github_actions_service_account" {
  description = "Service account email for GitHub Actions"
  value       = google_service_account.github_actions.email
}

# --- VPC ---------------------------------------------------------------------

output "vpc_connector_name" {
  description = "VPC connector name for Cloud Run"
  value       = google_vpc_access_connector.connector.name
}
