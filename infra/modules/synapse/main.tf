# Synapse-workspace med serverless SQL som exponerar gold-lagret för Power BI.

terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

resource "azurerm_synapse_workspace" "this" {
  name                                 = var.name
  resource_group_name                  = var.resource_group_name
  location                             = var.location
  storage_data_lake_gen2_filesystem_id = var.default_filesystem_id
  azuread_authentication_only          = true
  managed_resource_group_name          = "${var.resource_group_name}-syn-managed"
  tags                                 = var.tags

  identity {
    type = "SystemAssigned"
  }

  # Azure sätter ett standardvärde ("sqladminuser") även när bara Entra ID-inloggning
  # används. Utan ignore_changes ersätter Terraform hela workspacet vid varje apply.
  lifecycle {
    ignore_changes = [sql_administrator_login]
  }
}

# Krävs för att Azure-tjänster (t.ex. Power BI-tjänsten) ska nå endpointen.
resource "azurerm_synapse_firewall_rule" "azure_services" {
  name                 = "AllowAllWindowsAzureIps"
  synapse_workspace_id = azurerm_synapse_workspace.this.id
  start_ip_address     = "0.0.0.0"
  end_ip_address       = "0.0.0.0"
}

resource "azurerm_synapse_firewall_rule" "allowed" {
  for_each             = var.allowed_ip_ranges
  name                 = each.key
  synapse_workspace_id = azurerm_synapse_workspace.this.id
  start_ip_address     = each.value.start
  end_ip_address       = each.value.end
}

# Synapse läser gold-tabellerna (Delta) med sin managed identity.
resource "azurerm_role_assignment" "read_gold" {
  scope                = var.gold_container_id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azurerm_synapse_workspace.this.identity[0].principal_id
}

# Synapse behöver full åtkomst till sitt default filesystem.
resource "azurerm_role_assignment" "default_fs" {
  scope                = var.default_container_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_synapse_workspace.this.identity[0].principal_id
}

# Personer som ska administrera Synapse (Synapse Administrator ger full åtkomst till serverless SQL).
resource "azurerm_synapse_role_assignment" "admins" {
  for_each             = toset(var.admin_object_ids)
  synapse_workspace_id = azurerm_synapse_workspace.this.id
  role_name            = "Synapse Administrator"
  principal_id         = each.key

  depends_on = [azurerm_synapse_firewall_rule.allowed]
}

# Deploy-identiteten kör Synapse-SQL:en i CI. Den blir Synapse Administrator automatiskt när den
# skapar workspacet, men den tilldelningen får principal-typen User, och då nekas inloggningen
# till serverless SQL. Därför en explicit tilldelning som ServicePrincipal.
data "azurerm_client_config" "current" {}

resource "azurerm_synapse_role_assignment" "deployer_sql_admin" {
  synapse_workspace_id = azurerm_synapse_workspace.this.id
  role_name            = "Synapse SQL Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
  principal_type       = "ServicePrincipal"

  depends_on = [azurerm_synapse_firewall_rule.allowed]
}

# Power BI-workspacet kopplas som linked service manuellt i Synapse Studio
# (Manage → Linked services → Connect to Power BI), eftersom azurerm saknar stöd för det.
