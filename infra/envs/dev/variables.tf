variable "subscription_id" {
  type = string
}

variable "environment" {
  type = string
}

variable "location" {
  type    = string
  default = "swedencentral"
}

variable "storage_replication_type" {
  type    = string
  default = "LRS"
}

variable "admin_object_ids" {
  type    = list(string)
  default = []
}

variable "gold_reader_object_ids" {
  type    = list(string)
  default = []
}

variable "catalog_admins" {
  type    = list(string)
  default = []
}

variable "databricks_metastore_id" {
  type    = string
  default = null
}
