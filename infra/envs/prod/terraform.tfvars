environment              = "prod"
storage_replication_type = "ZRS"

# Fyll i: subscription_id sätts via TF_VAR_subscription_id (CI) eller här lokalt.
admin_object_ids = ["835b61b2-4b5a-4f6e-95da-de77fd990b26"]
# Power BI-användaren som läser gold direkt (se powerbi/README.md). Object ID enligt `az ad user show`.
gold_reader_object_ids = ["c9a37f05-09d5-4994-8dd5-aa464296ae6c"] # jonny-pbi-user
# catalog_admins sätts i CI från GitHub-secreten CATALOG_ADMIN_EMAIL (TF_VAR_catalog_admins).
