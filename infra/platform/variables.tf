variable "environment" {
  type = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment måste vara dev eller prod."
  }
}

variable "project" {
  type    = string
  default = "fallenleaves"
}

variable "location" {
  type    = string
  default = "swedencentral"
}

variable "catalog_prefix" {
  type    = string
  default = "fallen_leaves"
}

variable "storage_replication_type" {
  type    = string
  default = "LRS"
}

variable "admin_object_ids" {
  description = "Entra ID object ID för personer som administrerar projektet (Key Vault och Synapse)."
  type        = list(string)
  default     = []
}

variable "gold_reader_object_ids" {
  description = "Entra ID object ID som får läsa gold-containern direkt (Power BI)."
  type        = list(string)
  default     = []
}

variable "gold_reader_users" {
  description = "Databricks-användare (e-post) som får läsa schemat gold och publicera till Power BI."
  type        = list(string)
  default     = []
}

variable "catalog_admins" {
  description = "Databricks-användare/grupper som får ALL PRIVILEGES på catalogen."
  type        = list(string)
  default     = []
}

variable "databricks_metastore_id" {
  type    = string
  default = null
}

variable "synapse_allowed_ip_ranges" {
  description = "Brandväggsregler för Synapse-endpointen (se modules/synapse)."
  type = map(object({
    start = string
    end   = string
  }))
  default = {
    AllowAll = { start = "0.0.0.0", end = "255.255.255.255" }
  }
}

variable "tags" {
  type    = map(string)
  default = {}
}
