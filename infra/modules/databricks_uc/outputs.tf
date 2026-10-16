output "catalog_name" {
  value = databricks_catalog.this.name
}

output "secret_scope" {
  value = databricks_secret_scope.app.name
}
