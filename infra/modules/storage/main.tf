# ADLS Gen2 för medallion-lagren.
#   landing – rå JSON från API:erna (Databricks volume)
#   bronze  – rådata som Delta (append-only)
#   silver  – rensad och sammankopplad data
#   gold    – analysklara tabeller som Synapse läser
#   synapse – default filesystem för Synapse-workspacet

terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

locals {
  containers = toset(["landing", "bronze", "silver", "gold", "synapse"])
}

resource "azurerm_storage_account" "lake" {
  name                            = var.name
  resource_group_name             = var.resource_group_name
  location                        = var.location
  account_kind                    = "StorageV2"
  account_tier                    = "Standard"
  account_replication_type        = var.replication_type
  is_hns_enabled                  = true
  min_tls_version                 = "TLS1_2"
  shared_access_key_enabled       = false
  allow_nested_items_to_be_public = false
  tags                            = var.tags
}

resource "azurerm_storage_container" "this" {
  for_each           = local.containers
  name               = each.key
  storage_account_id = azurerm_storage_account.lake.id
}
