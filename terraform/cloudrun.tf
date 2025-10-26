##############################
# CLOUD RUN JOB (EXECUÇÃO ETL BRONZE)
##############################
resource "google_cloud_run_v2_job" "etl_bronze_job" {
  name     = "etl-bronze-job-${var.environment}"
  project  = var.project_id
  location = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.pipeline_sa.email
      timeout         = "1800s" # 30 minutos
      max_retries     = 1

      containers {
        image = "gcr.io/${var.project_id}/etl-bronze:latest"

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "DATASET_BRONZE"
          value = "abi_bronze"
        }

        env {
          name  = "BUCKET_NAME"
          value = google_storage_bucket.beverage_mvp.name
        }

        env {
          name  = "REGION"
          value = var.region
        }

        env {
          name  = "ENVIRONMENT"
          value = var.environment
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }

      execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
    }
  }

  depends_on = [
    google_service_account.pipeline_sa,
    google_storage_bucket.beverage_mvp,
    google_bigquery_dataset.abi_bronze,
    google_storage_bucket_iam_member.storage_object_admin,
  ]
}

##############################
# CLOUD RUN JOB (EXECUÇÃO ETL SILVER)
##############################
resource "google_cloud_run_v2_job" "etl_silver_job" {
  name     = "etl-silver-job-${var.environment}"
  project  = var.project_id
  location = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.pipeline_sa.email
      timeout         = "1800s" # 30 minutos
      max_retries     = 1

      containers {
        image = "gcr.io/${var.project_id}/etl-silver:latest"

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "DATASET_BRONZE"
          value = "abi_bronze"
        }

        env {
          name  = "DATASET_SILVER"
          value = "abi_silver"
        }

        env {
          name  = "REGION"
          value = var.region
        }

        env {
          name  = "ENVIRONMENT"
          value = var.environment
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }

      execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
    }
  }

  depends_on = [
    google_service_account.pipeline_sa,
    google_bigquery_dataset.abi_bronze,
    google_bigquery_dataset.abi_silver
  ]
}

##############################
# CLOUD RUN JOB (EXECUÇÃO ETL GOLD)
##############################
resource "google_cloud_run_v2_job" "etl_gold_job" {
  name     = "etl-gold-job-${var.environment}"
  project  = var.project_id
  location = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.pipeline_sa.email
      timeout         = "1800s" # 30 minutos
      max_retries     = 1

      containers {
        image = "gcr.io/${var.project_id}/etl-gold:latest"

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "DATASET_SILVER"
          value = "abi_silver"
        }

        env {
          name  = "DATASET_GOLD"
          value = "abi_gold"
        }

        env {
          name  = "REGION"
          value = var.region
        }

        env {
          name  = "ENVIRONMENT"
          value = var.environment
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }

      execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
    }
  }

  depends_on = [
    google_service_account.pipeline_sa,
    google_bigquery_dataset.abi_silver,
    google_bigquery_dataset.abi_gold
  ]
}

##############################
# CLOUD SCHEDULER (AGENDAMENTO DIÁRIO - BRONZE APENAS)
##############################
resource "google_cloud_scheduler_job" "etl_bronze_daily" {
  name        = "etl-bronze-daily-${var.environment}"
  project     = var.project_id
  description = "Executa o ETL Bronze diariamente às 2AM (${var.environment})"
  schedule    = "0 2 * * *" # 2h da manhã todos os dias
  time_zone   = "America/Sao_Paulo"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.etl_bronze_job.name}:run"

    oidc_token {
      service_account_email = google_service_account.pipeline_sa.email
    }
  }

  depends_on = [
    google_cloud_run_v2_job.etl_bronze_job,
    google_service_account.pipeline_sa
  ]
}