environment              = "dev"
storage_replication_type = "LRS"

# Fyll i: subscription_id sätts via TF_VAR_subscription_id (CI) eller här lokalt.
admin_object_ids = ["835b61b2-4b5a-4f6e-95da-de77fd990b26"]
# catalog_admins sätts i CI från GitHub-secreten CATALOG_ADMIN_EMAIL (TF_VAR_catalog_admins).
