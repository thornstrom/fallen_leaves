# Power BI-rapport

Rapporten läser gold-tabellerna (Delta) **direkt från ADLS Gen2** med Power BI:s
Azure Data Lake Storage Gen2-connector. Inloggningen sker med användarens Entra ID (OAuth),
eftersom storage-kontot har nycklar avstängda (`shared_access_key_enabled = false`).
Användaren får läsrätt på bara `gold`-containern.

```
Databricks ──► gold/delta/<tabell>/ (Delta, ADLS Gen2) ──► Power BI Desktop ──► Power BI Service
                                        ▲                        (OAuth)          (schemalagd uppdatering 06:00)
                     Storage Blob Data Reader på gold-containern
```

Spara rapporten som **Power BI-projekt (.pbip)** i den här mappen så versionshanteras modell och
rapport i git (Arkiv → Spara som → Power BI-projekt; aktivera först *Power BI Project (.pbip) save
option* under Alternativ → Förhandsversionsfunktioner).

## Förutsättningar

- **Ett jobb- eller skolkonto** med Power BI, t.ex. en användare i din Entra-tenant
  (`namn@<tenant>.onmicrosoft.com`) med Power BI Pro- eller Fabric-trial. Ett personligt
  Microsoft-konto kan inte logga in i Power BI.
- **Windows** för Power BI Desktop. Använd lab-VM:en nedan om du har Mac.

## 1. Ge Power BI-användaren läsrätt på gold

Hämta användarens object ID och lägg det i `gold_reader_object_ids` i `infra/envs/prod/terraform.tfvars`:

```bash
az ad user show --id namn@<tenant>.onmicrosoft.com --query id -o tsv
```

Merga till `main`, så tilldelar prod-deployen rollen *Storage Blob Data Reader* på `gold`-containern.
Det kan ta några minuter innan rollen gäller.

## 2. Starta lab-VM:en (bara på Mac)

`infra/lab/` skapar en Windows Server-VM med Power BI Desktop förinstallerat. RDP är bara öppet från
de adresser du anger, och VM:en stängs av kl. 22:00 varje kväll. Den använder lokal state.

```bash
cd infra/lab
cp terraform.tfvars.example terraform.tfvars   # fyll i subscription och din IP
terraform init && terraform apply
terraform output rdp_address
terraform output -raw admin_password
```

Anslut med *Windows App* (tidigare Microsoft Remote Desktop) på Mac. Ta bort VM:en med
`terraform destroy` när du är klar. Starta den igen efter avstängning med
`az vm start -g rg-fallenleaves-lab -n vm-fl-lab`.

## 3. Bygg rapporten

1. Öppna Power BI Desktop och logga in med jobbkontot.
2. Skapa parametern **StorageAccount** (Hem → Transformera data → Hantera parametrar → Ny, typ Text).
   Värde: `terraform output -raw storage_account_name` i `infra/envs/prod`.
3. Skapa frågorna i [`gold_queries.pq`](gold_queries.pq): funktionen `GoldTable` och tabellerna
   `daily_national`, `daily_national_autumn`, `daily_station_delay_weather` och `correlation_results`
   (Ny källa → Tom fråga → Avancerad redigerare).
4. När Power BI frågar efter inloggning: välj **Organisationskonto** och logga in med jobbkontot.
   Inloggningen gäller för `https://<konto>.dfs.core.windows.net`.
5. Lägg till måtten i [`measures.dax`](measures.dax).
6. Sidor:

| Sida | Visualisering | Fält |
|---|---|---|
| Översikt | Linjediagram, två y-axlar | `event_date`; `Medelförsening (min)`, `Medeltemperatur (°C)`; utsnitt på `region` |
| Samband | Punktdiagram | X: `temp_mean_c`, Y: `avg_arrival_delay_min`, detalj: `event_date`, förklaring: `region`; aktivera trendlinje (Analys → Trend line) |
| Temperaturfall | Punktdiagram | X: `temp_delta_c`, Y: `share_delayed_5` |
| Stationer | Karta (Azure Maps) | Latitud/longitud från `daily_station_delay_weather`, storlek: `n_arrivals`, färg: `avg_arrival_delay_min` |
| Statistik | Tabell | `correlation_results`: region, delay_metric, weather_metric, lag_days, n, pearson_r, spearman_rho, p_value_pearson, `Signifikant (p < 0,05)` |

Läs korrelationen tillsammans med `n`: med en höst data (≈ 60–90 dagar per region) är
resultaten preliminära, och trender över säsongen (t.ex. fler resenärer, banarbeten)
kan ge samband som inte orsakas av temperaturen.

## 4. Publicera och schemalägg uppdatering

1. Publicera till ett workspace i Power BI Service (Hem → Publicera).
2. I Power BI Service: semantikmodellen → **Inställningar → Autentiseringsuppgifter för datakälla**.
   Välj *OAuth2* och logga in med jobbkontot. Sekretessnivå: *Organisation*.
3. Under **Uppdatera**: aktivera schemalagd uppdatering kl. **06:00** (Europe/Stockholm). Databricks-jobbet
   startar 04:00 och är normalt klart långt innan.
4. Ingen gateway behövs, eftersom storage-kontot nås via sin publika endpoint och all åtkomst
   styrs av Entra ID och RBAC.

## Verifiera

- Uppdateringshistoriken i Power BI Service visar *Slutförd* dagen efter.
- `daily_national` innehåller gårdagens datum.
- Utan rollen på gold får uppdateringen 403 (`AuthorizationPermissionMismatch`), vilket visar
  att åtkomsten styrs av RBAC.

## Felsökning

| Fel | Orsak |
|---|---|
| 403 `AuthorizationPermissionMismatch` | Rollen saknas eller har inte slagit igenom än. Kontrollera `gold_reader_object_ids` och vänta några minuter. |
| `DeltaLake.Table` hittar ingen `_delta_log` | Fel sökväg. Tabellerna ligger under `gold/delta/<tabell>/`. |
| Inloggningen kräver nyckel eller SAS | Välj *Organisationskonto*. Nycklar är avstängda på kontot. |
| Tabellen kan inte läsas (okänd reader feature) | Tabellen använder en Delta-funktion som connectorn inte stöder. Gold skrivs utan deletion vectors; kontrollera tabellegenskaperna med `DESCRIBE DETAIL`. |

## Alternativ: via Synapse serverless

Vyerna i Synapse (`synapse/sql/20_views.sql`) finns kvar. Hämta data med *Azure Synapse Analytics SQL*
mot `terraform output -raw synapse_serverless_endpoint`, databasen `fallen_leaves`, och ge användaren
rollen `gold_reader`:

```sql
CREATE USER [namn@domän.se] FROM EXTERNAL PROVIDER;
ALTER ROLE gold_reader ADD MEMBER [namn@domän.se];
```
