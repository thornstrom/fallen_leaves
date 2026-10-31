# Lab: en Windows-VM med Power BI Desktop, eftersom Power BI Desktop inte finns för Mac.
# Fristående från plattformen och körs lokalt med lokal state (som bootstrap), så att den
# kan tas bort med `terraform destroy` när den inte används.

terraform {
  required_version = ">= 1.6"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

locals {
  name = "fallenleaves-lab"
  tags = {
    project     = "fallenleaves"
    environment = "lab"
    managed_by  = "terraform"
  }

  # Tyst installation av Power BI Desktop. Microsofts länk pekar alltid på senaste versionen.
  pbi_installer_url = "https://download.microsoft.com/download/8/8/0/880BCA75-79DD-466A-927D-1ABF1F5454B0/PBIDesktopSetup_x64.exe"
  install_pbi = join("; ", [
    "$f = 'C:\\PBIDesktopSetup_x64.exe'",
    "Invoke-WebRequest -Uri '${local.pbi_installer_url}' -OutFile $f -UseBasicParsing",
    "Start-Process $f -ArgumentList '-quiet','-norestart','ACCEPT_EULA=1' -Wait",
    "Remove-Item $f",
  ])
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name}"
  location = var.location
  tags     = local.tags
}

resource "azurerm_virtual_network" "this" {
  name                = "vnet-${local.name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  address_space       = ["10.50.0.0/24"]
  tags                = local.tags
}

resource "azurerm_subnet" "vm" {
  name                 = "snet-vm"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = ["10.50.0.0/27"]
}

# RDP öppnas bara från de adresser som anges i allowed_rdp_cidrs.
resource "azurerm_network_security_group" "vm" {
  name                = "nsg-${local.name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = local.tags

  security_rule {
    name                       = "AllowRdpFromAllowedIps"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "3389"
    source_address_prefixes    = var.allowed_rdp_cidrs
    destination_address_prefix = "*"
  }
}

resource "azurerm_subnet_network_security_group_association" "vm" {
  subnet_id                 = azurerm_subnet.vm.id
  network_security_group_id = azurerm_network_security_group.vm.id
}

resource "azurerm_public_ip" "vm" {
  name                = "pip-${local.name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.tags
}

resource "azurerm_network_interface" "vm" {
  name                = "nic-${local.name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = local.tags

  ip_configuration {
    name                          = "ipconfig"
    subnet_id                     = azurerm_subnet.vm.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.vm.id
  }
}

resource "random_password" "admin" {
  length      = 24
  min_upper   = 2
  min_lower   = 2
  min_numeric = 2
  min_special = 2
}

resource "azurerm_windows_virtual_machine" "this" {
  name                  = "vm-fl-lab"
  computer_name         = "fl-lab"
  resource_group_name   = azurerm_resource_group.this.name
  location              = var.location
  size                  = var.vm_size
  admin_username        = var.admin_username
  admin_password        = random_password.admin.result
  network_interface_ids = [azurerm_network_interface.vm.id]
  tags                  = local.tags

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
  }

  source_image_reference {
    publisher = "MicrosoftWindowsServer"
    offer     = "WindowsServer"
    sku       = "2022-datacenter-azure-edition"
    version   = "latest"
  }
}

resource "azurerm_virtual_machine_extension" "install_pbi" {
  name                 = "install-powerbi-desktop"
  virtual_machine_id   = azurerm_windows_virtual_machine.this.id
  publisher            = "Microsoft.Compute"
  type                 = "CustomScriptExtension"
  type_handler_version = "1.10"
  tags                 = local.tags

  protected_settings = jsonencode({
    commandToExecute = "powershell -NoProfile -ExecutionPolicy Bypass -Command \"${local.install_pbi}\""
  })
}

# Stänger av VM:en varje kväll så att den inte kostar i onödan.
resource "azurerm_dev_test_global_vm_shutdown_schedule" "this" {
  virtual_machine_id    = azurerm_windows_virtual_machine.this.id
  location              = var.location
  enabled               = true
  daily_recurrence_time = var.shutdown_time
  timezone              = "W. Europe Standard Time"
  tags                  = local.tags

  notification_settings {
    enabled = false
  }
}
