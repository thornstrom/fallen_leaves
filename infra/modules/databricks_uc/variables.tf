variable "environment" {
  type = string
}

variable "catalog_name" {
  type = string
}

variable "access_connector_id" {
  type = string
}

variable "abfss_urls" {
  description = "abfss-URL per container (från storage-modulen)."
  type        = map(string)
}

variable "metastore_id" {
  description = "Sätt bara om workspacet inte tilldelas en metastore automatiskt."
  type        = string
  default     = null
}

variable "workspace_numeric_id" {
  description = "Workspacets numeriska ID (krävs bara tillsammans med metastore_id)."
  type        = string
  default     = null
}

variable "catalog_admins" {
  description = "Användare eller grupper (e-post/gruppnamn) som får ALL PRIVILEGES på catalogen."
  type        = list(string)
  default     = []
}
