# Engångs-bootstrap: körs lokalt av en administratör med lokal state.
# Skapar
#   - storage account för Terraform-state (en container per miljö)
#   - en Entra ID-app per miljö med federated credentials för GitHub Actions (OIDC)
#   - GitHub-environments (dev, prod-plan, prod) och variabler som workflows läser

terraform {
  required_version = ">= 1.6"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id     = var.subscription_id
  storage_use_azuread = true
}

provider "azuread" {}

# Autentiserar med GITHUB_TOKEN i miljön, t.ex. `export GITHUB_TOKEN=$(gh auth token)`.
provider "github" {
  owner = var.github_owner
}

data "azurerm_client_config" "current" {}
data "azurerm_subscription" "current" {}

locals {
  repo_full_name = "${var.github_owner}/${var.github_repo}"

  # Miljöer i Azure (en state-container och en deploy-identitet per miljö).
  environments = toset(["dev", "prod"])

  # GitHub-environments och vilken Azure-identitet de använder.
  # prod-plan kör terraform plan på main utan godkännande, prod kräver godkännande för apply.
  github_environments = {
    dev       = "dev"
    prod-plan = "prod"
    prod      = "prod"
  }
}

resource "random_string" "suffix" {
  length  = 5
  upper   = false
  special = false
}

# ---------------------------------------------------------------------------
# Terraform-state
# ---------------------------------------------------------------------------

resource "azurerm_resource_group" "tfstate" {
  name     = "rg-${var.project}-tfstate"
  location = var.location
}

resource "azurerm_storage_account" "tfstate" {
  name                            = "st${var.project}tf${random_string.suffix.result}"
  resource_group_name             = azurerm_resource_group.tfstate.name
  location                        = azurerm_resource_group.tfstate.location
  account_tier                    = "Standard"
  account_replication_type        = "ZRS"
  min_tls_version                 = "TLS1_2"
  shared_access_key_enabled       = false
  allow_nested_items_to_be_public = false

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 30
    }
  }
}

resource "azurerm_storage_container" "tfstate" {
  for_each           = local.environments
  name               = "tfstate-${each.key}"
  storage_account_id = azurerm_storage_account.tfstate.id
}

# Administratören som kör bootstrap behöver också kunna läsa state lokalt.
resource "azurerm_role_assignment" "tfstate_admin" {
  scope                = azurerm_storage_account.tfstate.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}

# ---------------------------------------------------------------------------
# Deploy-identiteter (en per miljö) med OIDC från GitHub
# ---------------------------------------------------------------------------

resource "azuread_application" "deployer" {
  for_each     = local.environments
  display_name = "sp-${var.project}-github-${each.key}"
  owners       = [data.azurerm_client_config.current.object_id]
}

resource "azuread_service_principal" "deployer" {
  for_each  = local.environments
  client_id = azuread_application.deployer[each.key].client_id
  owners    = [data.azurerm_client_config.current.object_id]
}

resource "azuread_application_federated_identity_credential" "github" {
  for_each       = local.github_environments
  application_id = azuread_application.deployer[each.value].id
  display_name   = "github-${var.github_repo}-${each.key}"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${local.repo_full_name}:environment:${each.key}"
}

# Contributor för att skapa resurser och RBAC Administrator för att skapa rolltilldelningar
# (t.ex. Databricks access connector → storage). Avgränsat till subscriptionen.
resource "azurerm_role_assignment" "deployer_contributor" {
  for_each             = local.environments
  scope                = data.azurerm_subscription.current.id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.deployer[each.key].object_id
}

resource "azurerm_role_assignment" "deployer_rbac_admin" {
  for_each             = local.environments
  scope                = data.azurerm_subscription.current.id
  role_definition_name = "Role Based Access Control Administrator"
  principal_id         = azuread_service_principal.deployer[each.key].object_id
}

resource "azurerm_role_assignment" "deployer_tfstate" {
  for_each             = local.environments
  scope                = azurerm_storage_container.tfstate[each.key].id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azuread_service_principal.deployer[each.key].object_id
}

# ---------------------------------------------------------------------------
# GitHub-environments och variabler
# ---------------------------------------------------------------------------

data "github_user" "reviewers" {
  for_each = toset(var.prod_reviewers)
  username = each.key
}

resource "github_repository_environment" "env" {
  for_each    = local.github_environments
  repository  = var.github_repo
  environment = each.key

  dynamic "reviewers" {
    for_each = each.key == "prod" ? [1] : []
    content {
      users = [for u in data.github_user.reviewers : tonumber(u.id)]
    }
  }

  # prod-plan och prod får bara användas från main.
  dynamic "deployment_branch_policy" {
    for_each = each.key == "dev" ? [] : [1]
    content {
      protected_branches     = false
      custom_branch_policies = true
    }
  }
}

resource "github_repository_environment_deployment_policy" "main_only" {
  for_each       = { for k, v in local.github_environments : k => v if k != "dev" }
  repository     = var.github_repo
  environment    = github_repository_environment.env[each.key].environment
  branch_pattern = "main"
}

resource "github_actions_environment_variable" "client_id" {
  for_each      = local.github_environments
  repository    = var.github_repo
  environment   = github_repository_environment.env[each.key].environment
  variable_name = "AZURE_CLIENT_ID"
  value         = azuread_application.deployer[each.value].client_id
}

resource "github_actions_environment_variable" "tfstate_container" {
  for_each      = local.github_environments
  repository    = var.github_repo
  environment   = github_repository_environment.env[each.key].environment
  variable_name = "TFSTATE_CONTAINER"
  value         = azurerm_storage_container.tfstate[each.value].name
}

resource "github_actions_variable" "repo" {
  for_each = {
    AZURE_TENANT_ID         = data.azurerm_client_config.current.tenant_id
    AZURE_SUBSCRIPTION_ID   = data.azurerm_subscription.current.subscription_id
    TFSTATE_RESOURCE_GROUP  = azurerm_resource_group.tfstate.name
    TFSTATE_STORAGE_ACCOUNT = azurerm_storage_account.tfstate.name
  }
  repository    = var.github_repo
  variable_name = each.key
  value         = each.value
}
