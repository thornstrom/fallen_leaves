output "workspace_id" {
  description = "Azure resource-ID för workspacet."
  value       = azurerm_databricks_workspace.this.id
}

output "workspace_url" {
  value = "https://${azurerm_databricks_workspace.this.workspace_url}"
}

output "workspace_numeric_id" {
  description = "Databricks numeriska workspace-ID."
  value       = azurerm_databricks_workspace.this.workspace_id
}

output "access_connector_id" {
  value = azurerm_databricks_access_connector.this.id
}
