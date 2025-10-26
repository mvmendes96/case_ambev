variable "project_id" {
  type        = string
  description = "Google Cloud Project ID"
  default     = "ambev-2025"
  
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Invalid project ID format. Must be 6-30 characters, start with letter, and contain only lowercase letters, numbers, or hyphens."
  }
}

variable "region" {
  type        = string
  description = "Google Cloud region for resources"
  default     = "us-central1"
  
  validation {
    condition     = contains(["us-central1", "us-east1", "us-west1", "southamerica-east1", "europe-west1"], var.region)
    error_message = "Region must be one of: us-central1, us-east1, us-west1, southamerica-east1, europe-west1."
  }
}

variable "zone" {
  type        = string
  description = "Google Cloud zone for resources"
  default     = "us-central1-a"
}

variable "environment" {
  description = "Ambiente de implantação (dev, staging, prod)"
  type        = string
  default     = "dev"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

# Nova variável para configurações específicas por ambiente
variable "resource_settings" {
  description = "Configurações de recursos por ambiente"
  type = map(object({
    machine_type = string
    max_instances = number
    cpu_limit    = string
    memory_limit = string
  }))
  default = {
    dev = {
      machine_type  = "e2-micro"
      max_instances = 1
      cpu_limit     = "1"
      memory_limit  = "512Mi"
    }
    staging = {
      machine_type  = "e2-small"
      max_instances = 2
      cpu_limit     = "1"
      memory_limit  = "1Gi"
    }
    prod = {
      machine_type  = "e2-medium"
      max_instances = 5
      cpu_limit     = "2"
      memory_limit  = "2Gi"
    }
  }
}