output "name" {
  value = azurerm_synapse_workspace.this.name
}

output "serverless_endpoint" {
  value = azurerm_synapse_workspace.this.connectivity_endpoints["sqlOnDemand"]
}

output "web_url" {
  value = azurerm_synapse_workspace.this.connectivity_endpoints["web"]
}
