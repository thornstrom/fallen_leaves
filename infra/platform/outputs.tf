output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "databricks_host" {
  value = module.databricks_workspace.workspace_url
}

output "databricks_workspace_resource_id" {
  value = module.databricks_workspace.workspace_id
}

output "catalog_name" {
  value = module.databricks_uc.catalog_name
}

output "storage_account_name" {
  value = module.storage.account_name
}

output "gold_root" {
  description = "Rot för gold-tabellerna som Synapse läser."
  value       = "${module.storage.abfss_urls["gold"]}delta"
}

output "key_vault_name" {
  value = module.keyvault.name
}

output "synapse_serverless_endpoint" {
  value = module.synapse.serverless_endpoint
}

output "synapse_web_url" {
  value = module.synapse.web_url
}
