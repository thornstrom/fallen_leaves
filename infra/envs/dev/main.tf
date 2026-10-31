# Rotmodul för en miljö. dev/ och prod/ har identisk main.tf och skiljer sig bara i terraform.tfvars.

terraform {
  required_version = ">= 1.6"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Värdena sätts med -backend-config (se README och workflows).
  backend "azurerm" {
    key              = "platform.tfstate"
    use_azuread_auth = true
  }
}

# I GitHub Actions autentiserar azurerm med OIDC via ARM_USE_OIDC/ARM_CLIENT_ID m.fl.
# Lokalt används az login.
provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = false
    }
  }
  subscription_id     = var.subscription_id
  storage_use_azuread = true
}

# Databricks-providern pekar på workspacet som skapas i samma körning.
# Autentisering väljs med DATABRICKS_AUTH_TYPE (azure-cli både lokalt och i CI).
provider "databricks" {
  host                        = module.platform.databricks_host
  azure_workspace_resource_id = module.platform.databricks_workspace_resource_id
}

module "platform" {
  source = "../../platform"

  environment              = var.environment
  location                 = var.location
  storage_replication_type = var.storage_replication_type
  admin_object_ids         = var.admin_object_ids
  catalog_admins           = var.catalog_admins
  gold_reader_object_ids   = var.gold_reader_object_ids
  databricks_metastore_id  = var.databricks_metastore_id
}
