# Cloud Run requer uma imagem Docker pré-construída
# Vamos criar depois que tivermos o Dockerfile

# resource "google_cloud_run_service" "etl_beverage" {
#   name     = "etl-beverage"
#   location = var.region
# 
#   template {
#     spec {
#       containers {
#         image = "gcr.io/${var.project_id}/etl-beverage:latest"
#       }
#       service_account_name = google_service_account.pipeline_sa.email
#     }
#   }
# 
#   traffic {
#     percent         = 100
#     latest_revision = true
#   }
# 
#   depends_on = [google_service_account.pipeline_sa]
# }