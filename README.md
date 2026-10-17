# fallen_leaves

**Finns det ett samband mellan fallande temperaturer under hösten och förseningar i SJ:s tågtrafik?**

Projektet hämtar varje natt SJ:s tåglägen från Trafikverket och temperaturer från SMHI, kopplar
ihop dem i en medallion-arkitektur i Databricks och exponerar resultatet via Azure Synapse
serverless SQL för en Power BI-rapport.

```
Trafikverket API ─┐                    ┌─────────────── Databricks (Unity Catalog) ───────────────┐
 (TrainAnnouncement,│  ingest_*          │ bronze            silver                   gold            │
  TrainStation)    ├──────────► landing ─► rå JSON  ──────► fact_train_event ─────► daily_station_    │
SMHI Metobs ───────┘  (volume)  │ (Auto     (payload)       fact_weather_hourly      delay_weather    │
 (temp, nederbörd)              │  Loader)                 dim_location             daily_national   │
                                │                          map_source_location      correlation_     │
                                │                          bridge_location_weather  results          │
                                └──────────────────────────────────────────────────────────┬──────────┘
                                                                       Delta i gold-containern
                                                                                           ▼
                                                     Synapse serverless SQL (vyer) ──► Power BI
```

| Katalog | Innehåll |
|---|---|
| `bootstrap/` | Engångs-Terraform: state-lagring, deploy-identiteter (OIDC) och GitHub-environments |
| `infra/` | Terraform för plattformen. `platform/` är gemensam, `envs/dev` och `envs/prod` skiljer sig bara i `terraform.tfvars` |
| `databricks/` | Python-paketet `fallen_leaves` och Databricks Asset Bundle med jobben |
| `synapse/` | SQL för serverless-databasen och vyerna samt `deploy.sh` |
| `powerbi/` | Guide och DAX-mått för rapporten |
| `.github/` | CI/CD |

## Datamodell

Alla källor kopplas ihop i silver via två gemensamma nycklar:

- **`location_id`**: kanonisk plats på formen `<typ>:<källnyckel>`, till exempel `rail:Cst` (Stockholm C) eller `wx:98210` (SMHI Stockholm).
  Tabellen `silver.map_source_location` mappar varje källas egen nyckel `(source, source_key)` till ett `location_id`.
- **tid**: `ts_hour_utc` för timdata, och lokalt datum (Europe/Stockholm) för dygnsdata.

`silver.bridge_location_weather` kopplar varje tågstation till närmaste aktiva SMHI-station inom 50 km.

Gold innehåller tre tabeller:
- `daily_station_delay_weather`: en rad per station och dag.
- `daily_national`: en rad per landsdel och dag, plus en rad för hela Sverige. Värdena är viktade med antal ankomster.
- `correlation_results`: Pearson och Spearman med n och p-värde, per landsdel och med 0–2 dagars fördröjning.

Förseningsmåtten räknas på **ankomster** som inte är inställda. Tidiga ankomster räknas som 0 minuter.
"Sen" betyder mer än 5 minuter.

### Lägga till en ny källa

1. Skriv en klient i `databricks/src/fallen_leaves/sources/` och ett inläsningssteg i `ingest.py` som skriver NDJSON till landing.
2. Lägg till källan i `BRONZE_SOURCES` i `config.py`. Bronze läser då in den automatiskt.
3. Skriv en silver-transformation som sätter `location_id` och UTC-tid, och mappa källans platser i `conform_locations.py`.
4. Lägg till en task i `databricks/resources/jobs.yml` och använd tabellen i gold.

## Kom igång (en gång)

### Förutsättningar
- En Azure-subscription där du är **Owner**, eller Contributor plus User Access Administrator, och får skapa app-registreringar i Entra ID.
- **Databricks account admin** i ditt Databricks-konto, för Unity Catalog-behörigheter.
- Ett GitHub-repo, med `gh` inloggat.
- En API-nyckel från Trafikverket. Registrera dig gratis på https://api.trafikinfo.trafikverket.se/.
- Power BI Pro, för publicering.
- Lokalt: `terraform` ≥ 1.6, `az`, `databricks` CLI ≥ 0.230, `go-sqlcmd`, Python 3.10+ och Java 17 (för testerna).

### 1. Bootstrap
```bash
az login
export GITHUB_TOKEN=$(gh auth token)
cd bootstrap
cp terraform.tfvars.example terraform.tfvars   # fyll i
terraform init && terraform apply
```
Bootstrap använder **lokal state**. Spara `bootstrap/terraform.tfstate` på ett säkert ställe, eftersom git ignorerar den.

### 2. Fyll i miljövariablerna
I `infra/envs/{dev,prod}/terraform.tfvars` anger du `admin_object_ids` (ditt Entra ID object ID, `az ad signed-in-user show --query id -o tsv`).
Din e-post i Databricks läggs som secret, så att den inte syns i det publika repot eller i loggarna:
```bash
gh secret set CATALOG_ADMIN_EMAIL --body "du@example.com"
```

### 3. Första deployen (en gång per miljö)
Öppna en PR mot `main`. Workflowet `pr` skapar då dev-miljön. Första gången krävs några manuella steg
innan deployen går igenom. Kör om det misslyckade jobbet efter varje steg (`gh run rerun <run-id> --failed`).

**a. Logga in i Databricks-workspacet.** Terraform ger dig rättigheter på catalogen, men din användare
finns inte i Databricks förrän du har loggat in en gång. Annars stoppar apply med
`Could not find principal`. Workspace-adressen får du med `terraform -chdir=infra/envs/dev output -raw databricks_host`.

**b. Skapa en SQL-login för deploy-identiteten i Synapse.** Synapse registrerar identiteten som skapar
workspacet med dess object ID, men en app loggar in med sitt client ID, så CI nekas
(`Login failed for user '<token-identified principal>'`). Som Synapse-admin kör du, mot `master` på
serverless-endpointen (`terraform -chdir=infra/envs/dev output -raw synapse_serverless_endpoint`):
```bash
sqlcmd -S <serverless-endpoint> -d master --authentication-method ActiveDirectoryAzCli -b \
  -Q "CREATE LOGIN [sp-fallenleaves-github-dev] FROM EXTERNAL PROVIDER; ALTER SERVER ROLE sysadmin ADD MEMBER [sp-fallenleaves-github-dev];"
```

**c. Bara om Terraform stoppar vid Unity Catalog-objekten** (storage credential, external location och
catalog) saknar deploy-identiteten behörighet på metastoren. Som Databricks account admin kör du då, i workspacet:
```sql
GRANT CREATE STORAGE CREDENTIAL, CREATE EXTERNAL LOCATION, CREATE CATALOG
ON METASTORE TO `<client-id för sp-fallenleaves-github-dev>`;
```
Client-id finns i `terraform output deployer_client_ids` i `bootstrap/`.
Om workspacet inte tilldelas någon metastore automatiskt sätter du `databricks_metastore_id` i tfvars.

För prod gör du samma steg med `infra/envs/prod` och `sp-fallenleaves-github-prod`.

### 4. Lägg in Trafikverket-nyckeln
```bash
az keyvault secret set --vault-name "$(terraform -chdir=infra/envs/dev output -raw key_vault_name)" \
  --name trafikverket-api-key --value "<din nyckel>"
```
Deploy-workflowet kopierar nyckeln till Databricks secret scope `fallen-leaves`. Kör om workflowet,
eller kör `databricks secrets put-secret fallen-leaves trafikverket-api-key` manuellt.

### 5. Kör jobbet och skapa Synapse-vyerna
Schemat är pausat i dev. Kör jobbet manuellt:
```bash
cd databricks
DATABRICKS_HOST=$(terraform -chdir=../infra/envs/dev output -raw databricks_host) \
  databricks bundle run -t dev fallen_leaves_daily
```
Kör sedan om workflowet, eller `synapse/deploy.sh <endpoint> <gold_root>`, så att vyerna skapas.
Vyerna kräver att gold-tabellerna finns.

### 6. Prod
Merga PR:en. Workflowet `main` kör `terraform plan` för prod och visar planen i jobbsammanfattningen.
Efter godkännande i environmentet `prod` körs apply, och sedan deployas jobb och SQL. Upprepa steg 3–4 för prod.
I prod körs `fallen_leaves_daily` varje natt kl. 04:00 svensk tid.

### 7. Power BI
Se [`powerbi/README.md`](powerbi/README.md).

## CI/CD

| Händelse | Vad som händer |
|---|---|
| Pull request mot `main` | pytest, `terraform fmt`/`validate`, `plan` och `apply` i **dev**, `bundle deploy -t dev`, Synapse-SQL i dev |
| Push till `main` | Samma kontroller, `plan` för **prod** (environment `prod-plan`), sedan **manuellt godkännande** (environment `prod`), därefter `apply` av den granskade planen, `bundle deploy -t prod` och Synapse-SQL |

Inloggningen sker med OIDC (federated credentials). Det finns inga lösenord eller nycklar i GitHub.
Environmenten `prod-plan` och `prod` får bara användas från `main`.

## Lokal utveckling
```bash
python3 -m venv .venv && .venv/bin/pip install -e "databricks[dev]"
cd databricks && ../.venv/bin/pytest -q
```

## Kända begränsningar
- Trafikverkets API har bara kort historik, så data samlas in **från och med första prod-körningen**.
  Den första hösten ger därför ett begränsat underlag. Historisk data, till exempel från Trafiklabs arkiv, kan läggas till som en egen källa.
- Korrelation är inte orsakssamband. Säsongstrender, resandevolym och banarbeten kan samvariera med temperaturen.
- Synapse-brandväggen är öppen för alla IP-adresser, eftersom GitHub-hostade runners saknar fasta adresser och all inloggning sker via Entra ID.
  Begränsa `synapse_allowed_ip_ranges` i `infra/platform` om ni använder self-hosted runners.
- Gold skrivs utan deletion vectors, eftersom Synapse serverless inte kan läsa dem.
