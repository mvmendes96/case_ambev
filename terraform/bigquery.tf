##############################
# DATASET BRONZE (PARA DADOS BRUTOS PROCESSADOS)
##############################
resource "google_bigquery_dataset" "abi_bronze" {
  dataset_id                  = "abi_bronze"
  friendly_name               = "ABI Beverage Bronze Layer"
  description                 = "Camada bronze para dados brutos processados do pipeline beverage"
  location                    = var.region
  default_table_expiration_ms = 2592000000 # 30 dias

  labels = {
    environment = var.environment
    layer       = "bronze"
  }
}

##############################
# DATASET SILVER (PARA DADOS TRANSFORMADOS)
##############################
resource "google_bigquery_dataset" "abi_silver" {
  dataset_id                  = "abi_silver"
  friendly_name               = "ABI Beverage Silver Layer"
  description                 = "Camada silver para dados transformados e enriquecidos"
  location                    = var.region
  default_table_expiration_ms = 2592000000 # 30 dias

  labels = {
    environment = var.environment
    layer       = "silver"
  }
}

##############################
# DATASET GOLD (PARA DADOS CONSOLIDADOS)
##############################
resource "google_bigquery_dataset" "abi_gold" {
  dataset_id                  = "abi_gold"
  friendly_name               = "ABI Beverage Gold Layer"
  description                 = "Camada gold para dados consolidados e agregados"
  location                    = var.region
  default_table_expiration_ms = 2592000000 # 30 dias

  labels = {
    environment = var.environment
    layer       = "gold"
  }
}