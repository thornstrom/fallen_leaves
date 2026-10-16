# Hela plattformen för en miljö. Används av infra/envs/<env> så att dev och prod
# alltid har samma uppsättning resurser och bara skiljer sig i variabler.

terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
    databricks = {
      source = "databricks/databricks"
    }
    random = {
      source = "hashicorp/random"
    }
  }
}

locals {
  name = "${var.project}-${var.environment}"
  tags = merge(var.tags, {
    project     = var.project
    environment = var.environment
    managed_by  = "terraform"
  })
}

# Globalt unika namn (storage, key vault, synapse) behöver ett suffix.
resource "random_string" "suffix" {
  length  = 5
  upper   = false
  special = false
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name}"
  location = var.location
  tags     = local.tags
}

module "storage" {
  source              = "../modules/storage"
  name                = "stfl${var.environment}${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  replication_type    = var.storage_replication_type
  tags                = local.tags
}

module "keyvault" {
  source                    = "../modules/keyvault"
  name                      = "kv-fl-${var.environment}-${random_string.suffix.result}"
  resource_group_name       = azurerm_resource_group.this.name
  location                  = var.location
  purge_protection_enabled  = var.environment == "prod"
  secret_officer_object_ids = var.admin_object_ids
  tags                      = local.tags
}

module "databricks_workspace" {
  source              = "../modules/databricks_workspace"
  name                = "dbw-${local.name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  storage_account_id  = module.storage.account_id
  tags                = local.tags
}

module "databricks_uc" {
  source               = "../modules/databricks_uc"
  environment          = var.environment
  catalog_name         = "${var.catalog_prefix}_${var.environment}"
  access_connector_id  = module.databricks_workspace.access_connector_id
  abfss_urls           = module.storage.abfss_urls
  metastore_id         = var.databricks_metastore_id
  workspace_numeric_id = module.databricks_workspace.workspace_numeric_id
  catalog_admins       = var.catalog_admins

  # Rolltilldelningen för access connectorn måste finnas innan UC validerar sökvägarna.
  depends_on = [module.databricks_workspace]
}

module "synapse" {
  source                = "../modules/synapse"
  name                  = "syn-${local.name}-${random_string.suffix.result}"
  resource_group_name   = azurerm_resource_group.this.name
  location              = var.location
  default_filesystem_id = module.storage.synapse_filesystem_id
  default_container_id  = module.storage.container_ids["synapse"]
  gold_container_id     = module.storage.container_ids["gold"]
  admin_object_ids      = var.admin_object_ids
  allowed_ip_ranges     = var.synapse_allowed_ip_ranges
  tags                  = local.tags
}
