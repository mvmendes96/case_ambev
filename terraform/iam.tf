# iam.tf - Permissões corrigidas
resource "google_service_account" "pipeline_sa" {
  account_id   = "pipeline-sa-${var.environment}"
  display_name = "Service Account para Pipeline Beverage (${var.environment})"
  description  = "Service Account para executar ETL Bronze no ambiente ${var.environment}"
}

# Permissões ESPECÍFICAS para Storage
resource "google_storage_bucket_iam_member" "storage_object_admin" {
  bucket = google_storage_bucket.beverage_mvp.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# Permissão para LISTAR buckets (necessária para bucket.exists())
resource "google_project_iam_member" "storage_object_viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# Permissão para ACESSAR buckets (get)
resource "google_storage_bucket_iam_member" "storage_legacy_bucket_reader" {
  bucket = google_storage_bucket.beverage_mvp.name
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# Permissões BigQuery
resource "google_project_iam_member" "bq_data_owner" {
  project = var.project_id
  role    = "roles/bigquery.dataOwner"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

resource "google_project_iam_member" "bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# Permissões Cloud Run
resource "google_project_iam_member" "run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# Permissão para o Cloud Run executar como a service account
resource "google_project_iam_member" "run_service_agent" {
  project = var.project_id
  role    = "roles/run.serviceAgent"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# Permissões Cloud Scheduler
resource "google_project_iam_member" "cloud_scheduler_service_agent" {
  project = var.project_id
  role    = "roles/cloudscheduler.serviceAgent"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# Permissões para logging e monitoring
resource "google_project_iam_member" "logging_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

resource "google_project_iam_member" "monitoring_metricWriter" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}