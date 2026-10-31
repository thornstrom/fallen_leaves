output "rdp_address" {
  value = azurerm_public_ip.vm.ip_address
}

output "admin_username" {
  value = var.admin_username
}

output "admin_password" {
  description = "Visa med `terraform output -raw admin_password`."
  value       = random_password.admin.result
  sensitive   = true
}
