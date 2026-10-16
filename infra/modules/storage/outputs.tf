output "account_id" {
  value = azurerm_storage_account.lake.id
}

output "account_name" {
  value = azurerm_storage_account.lake.name
}

output "container_ids" {
  description = "Resource manager-ID per container."
  value       = { for k, c in azurerm_storage_container.this : k => c.id }
}

output "abfss_urls" {
  description = "abfss-URL per container, med avslutande snedstreck."
  value = {
    for k in keys(azurerm_storage_container.this) :
    k => "abfss://${k}@${azurerm_storage_account.lake.name}.dfs.core.windows.net/"
  }
}

output "synapse_filesystem_id" {
  description = "Data Lake Gen2-filesystem-ID i det format Synapse kräver."
  value       = "https://${azurerm_storage_account.lake.name}.dfs.core.windows.net/${azurerm_storage_container.this["synapse"].name}"
}
