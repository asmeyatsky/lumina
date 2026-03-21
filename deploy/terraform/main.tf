# =============================================================================
# LUMINA — GCP Infrastructure (Terraform)
# =============================================================================

terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "lumina-terraform-state"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# =============================================================================
# Enable required APIs
# =============================================================================
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "vpcaccess.googleapis.com",
    "compute.googleapis.com",
    "servicenetworking.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# =============================================================================
# VPC Network
# =============================================================================
resource "google_compute_network" "main" {
  name                    = "${var.project_name}-vpc"
  auto_create_subnetworks = false

  depends_on = [google_project_service.apis]
}

resource "google_compute_subnetwork" "main" {
  name          = "${var.project_name}-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.main.id
}

# Private services access for Cloud SQL
resource "google_compute_global_address" "private_ip_range" {
  name          = "${var.project_name}-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private_vpc" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
}

# =============================================================================
# VPC Connector (Cloud Run -> Cloud SQL)
# =============================================================================
resource "google_vpc_access_connector" "connector" {
  name          = "${var.project_name}-vpc-connector"
  region        = var.region
  network       = google_compute_network.main.name
  ip_cidr_range = "10.8.0.0/28"
  min_instances = 2
  max_instances = 3

  depends_on = [google_project_service.apis]
}

# =============================================================================
# Artifact Registry
# =============================================================================
resource "google_artifact_registry_repository" "docker" {
  location      = var.region
  repository_id = "${var.project_name}-docker"
  description   = "LUMINA Docker images"
  format        = "DOCKER"

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }

  depends_on = [google_project_service.apis]
}

# =============================================================================
# Cloud SQL — PostgreSQL 16
# =============================================================================
resource "google_sql_database_instance" "postgres" {
  name             = "${var.project_name}-db"
  database_version = "POSTGRES_16"
  region           = var.region

  deletion_protection = var.environment == "production"

  settings {
    tier              = var.db_tier
    availability_type = var.environment == "production" ? "REGIONAL" : "ZONAL"
    disk_size         = var.db_disk_size
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.main.id
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = var.environment == "production"
      start_time                     = "03:00"
      transaction_log_retention_days = 7

      backup_retention_settings {
        retained_backups = 14
      }
    }

    maintenance_window {
      day          = 7
      hour         = 4
      update_track = "stable"
    }

    database_flags {
      name  = "max_connections"
      value = "200"
    }

    insights_config {
      query_insights_enabled  = true
      query_plans_per_minute  = 5
      query_string_length     = 4096
      record_application_tags = true
      record_client_address   = true
    }
  }

  depends_on = [google_service_networking_connection.private_vpc]
}

resource "google_sql_database" "lumina" {
  name     = "lumina"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "lumina" {
  name     = "lumina"
  instance = google_sql_database_instance.postgres.name
  password = random_password.db_password.result
}

resource "random_password" "db_password" {
  length  = 32
  special = false
}

# =============================================================================
# Secret Manager
# =============================================================================
locals {
  secrets = {
    "database-url"       = "postgresql://lumina:${random_password.db_password.result}@${google_sql_database_instance.postgres.private_ip_address}:5432/lumina"
    "jwt-secret"         = random_password.jwt_secret.result
    "anthropic-api-key"  = var.anthropic_api_key
    "openai-api-key"     = var.openai_api_key
    "google-ai-api-key"  = var.google_ai_api_key
    "perplexity-api-key" = var.perplexity_api_key
    "neo4j-uri"          = var.neo4j_uri
    "neo4j-password"     = var.neo4j_password
    "pinecone-api-key"   = var.pinecone_api_key
    "redis-url"          = var.redis_url
    "sendgrid-api-key"   = var.sendgrid_api_key
    "slack-webhook-url"  = var.slack_webhook_url
  }
}

resource "random_password" "jwt_secret" {
  length  = 64
  special = true
}

resource "google_secret_manager_secret" "secrets" {
  for_each  = local.secrets
  secret_id = each.key

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "secrets" {
  for_each    = local.secrets
  secret      = google_secret_manager_secret.secrets[each.key].id
  secret_data = each.value
}

# =============================================================================
# Service Accounts
# =============================================================================
resource "google_service_account" "backend" {
  account_id   = "${var.project_name}-backend-sa"
  display_name = "LUMINA Backend Service Account"
}

resource "google_service_account" "frontend" {
  account_id   = "${var.project_name}-frontend-sa"
  display_name = "LUMINA Frontend Service Account"
}

# Grant backend SA access to secrets
resource "google_secret_manager_secret_iam_member" "backend_secret_access" {
  for_each  = google_secret_manager_secret.secrets
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.backend.email}"
}

# Grant backend SA access to Cloud SQL
resource "google_project_iam_member" "backend_cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

# =============================================================================
# Cloud Run — Backend
# =============================================================================
resource "google_cloud_run_v2_service" "backend" {
  name     = "${var.project_name}-backend"
  location = var.region

  template {
    service_account = google_service_account.backend.email

    scaling {
      min_instance_count = var.environment == "production" ? 1 : 0
      max_instance_count = 10
    }

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}/backend:latest"

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
        cpu_idle = false
      }

      startup_probe {
        http_get {
          path = "/health"
          port = 8000
        }
        initial_delay_seconds = 5
        period_seconds        = 5
        failure_threshold     = 10
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 8000
        }
        period_seconds    = 30
        failure_threshold = 3
      }

      dynamic "env" {
        for_each = local.secrets
        content {
          name = upper(replace(env.key, "-", "_"))
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secrets[env.key].secret_id
              version = "latest"
            }
          }
        }
      }

      env {
        name  = "LOG_LEVEL"
        value = var.environment == "production" ? "info" : "debug"
      }

      env {
        name  = "CORS_ORIGINS"
        value = var.domain_name != "" ? "https://${var.domain_name}" : "*"
      }
    }

    max_instance_request_concurrency = 100
  }

  depends_on = [
    google_secret_manager_secret_version.secrets,
    google_project_service.apis,
  ]
}

# Allow unauthenticated access to backend
resource "google_cloud_run_v2_service_iam_member" "backend_public" {
  name     = google_cloud_run_v2_service.backend.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# =============================================================================
# Cloud Run — Frontend
# =============================================================================
resource "google_cloud_run_v2_service" "frontend" {
  name     = "${var.project_name}-frontend"
  location = var.region

  template {
    service_account = google_service_account.frontend.email

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}/frontend:latest"

      ports {
        container_port = 80
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
        cpu_idle = true
      }

      startup_probe {
        http_get {
          path = "/"
          port = 80
        }
        initial_delay_seconds = 2
        period_seconds        = 3
        failure_threshold     = 5
      }
    }
  }

  depends_on = [google_project_service.apis]
}

# Allow unauthenticated access to frontend
resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  name     = google_cloud_run_v2_service.frontend.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# =============================================================================
# Cloud Load Balancer (HTTPS with custom domain)
# =============================================================================
resource "google_compute_region_network_endpoint_group" "backend_neg" {
  count = var.domain_name != "" ? 1 : 0

  name                  = "${var.project_name}-backend-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region

  cloud_run {
    service = google_cloud_run_v2_service.backend.name
  }
}

resource "google_compute_region_network_endpoint_group" "frontend_neg" {
  count = var.domain_name != "" ? 1 : 0

  name                  = "${var.project_name}-frontend-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region

  cloud_run {
    service = google_cloud_run_v2_service.frontend.name
  }
}

resource "google_compute_backend_service" "backend" {
  count = var.domain_name != "" ? 1 : 0

  name                  = "${var.project_name}-backend-bs"
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.backend_neg[0].id
  }
}

resource "google_compute_backend_service" "frontend" {
  count = var.domain_name != "" ? 1 : 0

  name                  = "${var.project_name}-frontend-bs"
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.frontend_neg[0].id
  }
}

resource "google_compute_url_map" "main" {
  count = var.domain_name != "" ? 1 : 0

  name            = "${var.project_name}-url-map"
  default_service = google_compute_backend_service.frontend[0].id

  host_rule {
    hosts        = [var.domain_name]
    path_matcher = "main"
  }

  path_matcher {
    name            = "main"
    default_service = google_compute_backend_service.frontend[0].id

    path_rule {
      paths   = ["/api/*", "/health", "/docs", "/openapi.json"]
      service = google_compute_backend_service.backend[0].id
    }
  }
}

resource "google_compute_managed_ssl_certificate" "main" {
  count = var.domain_name != "" ? 1 : 0

  name = "${var.project_name}-ssl-cert"

  managed {
    domains = [var.domain_name]
  }
}

resource "google_compute_target_https_proxy" "main" {
  count = var.domain_name != "" ? 1 : 0

  name             = "${var.project_name}-https-proxy"
  url_map          = google_compute_url_map.main[0].id
  ssl_certificates = [google_compute_managed_ssl_certificate.main[0].id]
}

resource "google_compute_global_forwarding_rule" "main" {
  count = var.domain_name != "" ? 1 : 0

  name                  = "${var.project_name}-https-rule"
  target                = google_compute_target_https_proxy.main[0].id
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# HTTP -> HTTPS redirect
resource "google_compute_url_map" "http_redirect" {
  count = var.domain_name != "" ? 1 : 0

  name = "${var.project_name}-http-redirect"

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "http_redirect" {
  count = var.domain_name != "" ? 1 : 0

  name    = "${var.project_name}-http-redirect-proxy"
  url_map = google_compute_url_map.http_redirect[0].id
}

resource "google_compute_global_forwarding_rule" "http_redirect" {
  count = var.domain_name != "" ? 1 : 0

  name                  = "${var.project_name}-http-redirect-rule"
  target                = google_compute_target_http_proxy.http_redirect[0].id
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# =============================================================================
# Workload Identity Federation (for GitHub Actions)
# =============================================================================
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "${var.project_name}-github-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Identity pool for GitHub Actions CI/CD"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub Provider"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  attribute_condition = "assertion.repository == '${var.github_repo}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "github_actions" {
  account_id   = "${var.project_name}-github-sa"
  display_name = "GitHub Actions Service Account"
}

resource "google_service_account_iam_member" "github_workload_identity" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

# Grant GitHub Actions SA the permissions it needs
resource "google_project_iam_member" "github_actions_roles" {
  for_each = toset([
    "roles/run.admin",
    "roles/artifactregistry.writer",
    "roles/iam.serviceAccountUser",
    "roles/cloudsql.client",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}
