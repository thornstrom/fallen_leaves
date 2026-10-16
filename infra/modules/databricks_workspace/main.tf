# Azure-delen av Databricks: workspace och access connector (managed identity som
# Unity Catalog använder för att läsa och skriva i data lake).

terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

resource "azurerm_databricks_workspace" "this" {
  name                        = var.name
  resource_group_name         = var.resource_group_name
  location                    = var.location
  sku                         = "premium" # krävs för Unity Catalog
  managed_resource_group_name = "${var.resource_group_name}-dbx-managed"
  tags                        = var.tags
}

resource "azurerm_databricks_access_connector" "this" {
  name                = "${var.name}-ac"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_role_assignment" "connector_storage" {
  scope                = var.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_databricks_access_connector.this.identity[0].principal_id
}
