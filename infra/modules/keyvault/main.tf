# Key Vault för API-nycklar. Hemligheterna själva sätts utanför Terraform
# (az keyvault secret set …) så att de aldrig hamnar i state. Deploy-workflowet
# kopierar dem till Databricks secret scope.

terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "this" {
  name                       = var.name
  resource_group_name        = var.resource_group_name
  location                   = var.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  purge_protection_enabled   = var.purge_protection_enabled
  soft_delete_retention_days = 7
  tags                       = var.tags
}

# Deploy-identiteten läser hemligheterna för att synka dem till Databricks.
resource "azurerm_role_assignment" "deployer_secrets_user" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "secret_officers" {
  for_each             = toset(var.secret_officer_object_ids)
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = each.key
}
