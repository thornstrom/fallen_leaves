output "databricks_host" {
  value = module.platform.databricks_host
}

output "catalog_name" {
  value = module.platform.catalog_name
}

output "gold_root" {
  value = module.platform.gold_root
}

output "storage_account_name" {
  value = module.platform.storage_account_name
}

output "key_vault_name" {
  value = module.platform.key_vault_name
}

output "synapse_serverless_endpoint" {
  value = module.platform.synapse_serverless_endpoint
}

output "synapse_web_url" {
  value = module.platform.synapse_web_url
}
