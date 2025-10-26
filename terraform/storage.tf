resource "google_storage_bucket" "beverage_mvp" {
  name     = "ambev-beverage-mvp"
  location = var.region
}