output "tfstate_resource_group" {
  value = azurerm_resource_group.tfstate.name
}

output "tfstate_storage_account" {
  value = azurerm_storage_account.tfstate.name
}

output "deployer_client_ids" {
  description = "Client ID för deploy-identiteten per miljö."
  value       = { for k, app in azuread_application.deployer : k => app.client_id }
}

output "backend_config_hint" {
  description = "Kör så här för att initiera en miljö lokalt."
  value       = <<-EOT
    cd infra/envs/<env>
    terraform init \
      -backend-config="resource_group_name=${azurerm_resource_group.tfstate.name}" \
      -backend-config="storage_account_name=${azurerm_storage_account.tfstate.name}" \
      -backend-config="container_name=tfstate-<env>"
  EOT
}
