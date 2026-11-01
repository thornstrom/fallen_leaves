# Unity Catalog-objekt i workspacet: credential, external locations, catalog,
# schemas för medallion-lagren, volumes för landning och checkpoints, samt secret scope.
#
# Förutsätter att workspacet är tilldelat en metastore. Nya workspaces tilldelas
# automatiskt regionens metastore. Annars, sätt var.metastore_id.

terraform {
  required_providers {
    databricks = {
      source = "databricks/databricks"
    }
  }
}

locals {
  locations = ["landing", "bronze", "silver", "gold"]
}

resource "databricks_metastore_assignment" "this" {
  count        = var.metastore_id == null ? 0 : 1
  metastore_id = var.metastore_id
  workspace_id = var.workspace_numeric_id
}

resource "databricks_storage_credential" "lake" {
  name    = "${var.catalog_name}_lake"
  comment = "Managed identity (access connector) för data lake i ${var.catalog_name}"

  azure_managed_identity {
    access_connector_id = var.access_connector_id
  }

  depends_on = [databricks_metastore_assignment.this]
}

resource "databricks_external_location" "this" {
  for_each        = toset(local.locations)
  name            = "${var.catalog_name}_${each.key}"
  url             = var.abfss_urls[each.key]
  credential_name = databricks_storage_credential.lake.name
  comment         = "${each.key}-container för ${var.catalog_name}"
}

resource "databricks_catalog" "this" {
  name         = var.catalog_name
  comment      = "fallen_leaves: tågförseningar och väder (${var.environment})"
  storage_root = "${var.abfss_urls["silver"]}_catalog"

  depends_on = [databricks_external_location.this]
}

resource "databricks_schema" "layer" {
  for_each     = toset(["bronze", "silver", "gold"])
  catalog_name = databricks_catalog.this.name
  name         = each.key
  # Managed tabeller hamnar under _managed. Gold-tabellerna skrivs som external
  # tables under gold/delta/ så att Synapse kan läsa dem på förutsägbara sökvägar.
  storage_root = "${var.abfss_urls[each.key]}_managed"

  depends_on = [databricks_external_location.this]
}

resource "databricks_volume" "landing" {
  name             = "landing"
  catalog_name     = databricks_catalog.this.name
  schema_name      = databricks_schema.layer["bronze"].name
  volume_type      = "EXTERNAL"
  storage_location = var.abfss_urls["landing"]
  comment          = "Rå JSON från källornas API:er"
}

resource "databricks_volume" "checkpoints" {
  name         = "checkpoints"
  catalog_name = databricks_catalog.this.name
  schema_name  = databricks_schema.layer["bronze"].name
  volume_type  = "MANAGED"
  comment      = "Checkpoints och schemaplatser för Auto Loader"
}

# databricks_grants äger alla grants på catalogen, så både admins och gold-läsare
# måste ligga i samma resurs.
resource "databricks_grants" "catalog" {
  count   = length(var.catalog_admins) + length(var.gold_reader_users) == 0 ? 0 : 1
  catalog = databricks_catalog.this.name

  dynamic "grant" {
    for_each = var.catalog_admins
    content {
      principal  = grant.value
      privileges = ["ALL_PRIVILEGES"]
    }
  }

  dynamic "grant" {
    for_each = var.gold_reader_users
    content {
      principal  = grant.value
      privileges = ["USE_CATALOG"]
    }
  }

  depends_on = [databricks_user.gold_reader]
}

# Power BI-användare som publicerar gold-tabellerna till Power BI från Catalog Explorer.
# De läser bara gold och kör frågor via workspacets SQL-warehouse (gruppen users har CAN_USE).
resource "databricks_user" "gold_reader" {
  for_each  = toset(var.gold_reader_users)
  user_name = each.value
}

resource "databricks_grants" "gold_schema" {
  count  = length(var.gold_reader_users) == 0 ? 0 : 1
  schema = "${databricks_catalog.this.name}.${databricks_schema.layer["gold"].name}"

  dynamic "grant" {
    for_each = var.gold_reader_users
    content {
      principal  = grant.value
      privileges = ["USE_SCHEMA", "SELECT"]
    }
  }

  depends_on = [databricks_user.gold_reader]
}

# Databricks-hanterat scope: Key Vault-backade scopes kan inte skapas av en service principal.
# Värdena kopieras från Key Vault av deploy-workflowet (se .github/actions/deploy-app).
resource "databricks_secret_scope" "app" {
  name = "fallen-leaves"
}
