# Power BI-rapport

Rapporten *Fallande löv* ligger i Power BI Service och byggs helt i webbläsaren, så det behövs varken
Windows eller Power BI Desktop. Gold-tabellerna publiceras från Databricks Catalog Explorer till en
semantisk modell i Power BI. Modellen importerar data via SQL-warehouset och uppdateras varje morgon.

```
Databricks (Unity Catalog)                         Power BI Service (workspace "Fallande löv", PPU)
fallen_leaves_prod.gold.* ── Publish to Power BI ─► semantisk modell fallen_leaves_prod-gold (Import, OAuth)
        ▲                       (Catalog Explorer)        │  schemalagd uppdatering 06:00
        │ SELECT via Serverless Starter Warehouse         ▼
        └──────────────────────────────────────── rapport "Fallande löv" (5 sidor)
```

## Förutsättningar

- **Ett jobb- eller skolkonto** i Entra-tenanten (`namn@<tenant>.onmicrosoft.com`). Ett personligt
  Microsoft-konto kan inte logga in i Power BI, och publiceringen fungerar bara för användare i sin
  hemtenant (inte gäster).
- **Power BI Premium Per User (PPU)**. Den kostnadsfria Power BI-utvärderingen (60 dagar) räcker.
  Publiceringen kräver Premium, PPU eller Fabric. Pro räcker inte. Fabric-trial behövs inte.
- **XMLA-slutpunkten** satt till *Read Write*: Administratörsportal → Premium Per User → XMLA Endpoint.
  Det kräver rollen *Fabric Administrator* (eller *Power BI Administrator*) i Entra.

## 1. Ge användaren tillgång i Databricks

Lägg e-postadressen i `gold_reader_users` i `infra/envs/prod/terraform.tfvars` och merga till `main`:

```hcl
gold_reader_users = ["namn@<tenant>.onmicrosoft.com"]
```

Prod-deployen lägger till användaren i workspacet med entitlements `workspace-access` och
`databricks-sql-access`, och ger `USE_CATALOG` på catalogen och `USE_SCHEMA` + `SELECT` på `gold`.
Gruppen `users` har redan `CAN_USE` på *Serverless Starter Warehouse*.

Kontrollera genom att logga in som användaren direkt på workspace-URL:en (inte via *Launch Workspace* i
Azure-portalen) och öppna Catalog → `fallen_leaves_prod` → `gold` → en tabell → *Sample Data*.

## 2. Skapa workspace i Power BI

På app.powerbi.com: Arbetsytor → Ny arbetsyta → namn *Fallande löv* → Avancerat → licensläge
**Premium per användare**.

## 3. Publicera gold från Databricks

1. Logga in i Databricks som Power BI-användaren och öppna Catalog → `fallen_leaves_prod` → **schemat `gold`**.
2. Välj *Serverless Starter Warehouse* uppe till vänster. **Warehouset måste vara igång**, annars är
   publiceringsknappen grå. Starta det vid behov:
   `databricks warehouses start <warehouse-id>`.
3. **Use with BI tools → Publish to Power BI workspace → Connect to Microsoft Entra ID**. Godkänn appen
   *Databricks Dataset Publishing Integration* om du blir tillfrågad.
4. Välj workspace *Fallande löv*, **Publish new semantic model**, lagringsläge **Import**, alla tre
   tabellerna och autentisering **OAuth**. Klicka **Publish to Power BI**.

Modellen heter `fallen_leaves_prod-gold`. Import ger snabba rapporter och warehouset startar bara vid
uppdateringen. Med DirectQuery startar det varje gång någon öppnar rapporten.

## 4. Inloggning och schemalagd uppdatering

Semantiska modellens inställningar i Power BI Service:

1. **Autentiseringsuppgifter för datakälla** → Redigera → **OAuth2**, sekretessnivå *Organisation* → Logga in.
2. **Uppdatera** → tidszon *(UTC+01:00) … Stockholm …* → aktivera schema → dagligen **06:00**.
   Databricks-jobbet startar 04:00 och är klart långt innan.
3. Kör *Uppdatera nu* och kontrollera att uppdateringshistoriken visar *Slutförd*.

Ingen gateway behövs.

## 5. Mått

Öppna modellen → **Redigering** → **DAX-frågevy**, klistra in [`measures.dax`](measures.dax) och klicka
**Uppdatera modellen med ändringar**. Kör frågan först och kontrollera att värdena är rimliga.

## 6. Rapportsidor

Skapa rapporten från modellen (Ny rapport) och spara den som *Fallande löv*.

| Sida | Visualisering | Fält |
|---|---|---|
| Översikt | Linjediagram | X: `event_date`, Y: `Medelförsening (min)`, sekundär Y: `Medeltemperatur (°C)`; utsnitt på `region` med **Sverige** förvalt |
| Samband | Punktdiagram | Värden: `event_date`, X: `temp_mean_c`, Y: `avg_arrival_delay_min`, förklaring: `region` |
| Temperaturfall | Punktdiagram | Värden: `event_date`, X: `temp_delta_c`, Y: `share_delayed_5`, förklaring: `region` |
| Stationer | Azure Maps | Latitud/longitud från `daily_station_delay_weather` (**Summera inte**), storlek: `n_arrivals`, knappbeskrivning: `station_name`, medel av `avg_arrival_delay_min` |
| Statistik | Tabell | `correlation_results`: region, delay_metric, weather_metric, lag_days, n, pearson_r, spearman_rho, p_value_pearson (alla tal **Summera inte**), `Signifikant (p < 0,05)` |

Två saker att tänka på:

- `region` innehåller både landsdelarna och **Sverige** (hela landet). Utan filter räknas varje tåg
  två gånger i måtten. Välj antingen Sverige eller en eller flera landsdelar.
- Numeriska kolumner summeras som standard. I Statistik-tabellen och för kartans koordinater ska de stå
  på *Summera inte*, annars slås raderna ihop och `Signifikant` blir fel.

Läs korrelationen tillsammans med `n`: med en höst data (≈ 60–90 dagar per region) är resultaten
preliminära, och trender över säsongen (t.ex. fler resenärer, banarbeten) kan ge samband som inte
orsakas av temperaturen.

## Verifiera

- Uppdateringshistoriken visar *Slutförd* dagen efter.
- Översikt-sidans linje slutar på gårdagens datum.

## Felsökning

| Fel | Orsak |
|---|---|
| *does not have Owner role, Contributor role …* vid inloggning i Databricks | Användaren saknar entitlement `workspace-access`. Kontrollera `gold_reader_users` och att prod-deployen gått igenom. |
| *Publish to Power BI* är grå, *Please ensure that the selected compute is running* | Starta SQL-warehouset. |
| *Power BI Premium is required* / workspace saknas i listan | Workspacet måste ha licensläge PPU och användaren en PPU-licens eller -utvärdering. |
| *Need admin approval* vid Connect to Microsoft Entra ID | Användarmedgivande är blockerat. En Global Admin godkänner appen *Databricks Dataset Publishing Integration* i Entra. |
| Uppdateringen misslyckas med inloggningsfel | Sätt om OAuth2 under *Autentiseringsuppgifter för datakälla*. |
| *Det finns ingen utvärderingsversion av Fabric för ditt konto* | Fabric-trial erbjuds inte alla tenanter. Den behövs inte för den här vägen. |

## Alternativ: Power BI Desktop direkt mot ADLS Gen2

Gold-tabellerna kan också läsas direkt som Delta från `gold`-containern med Power BI Desktop, utan
Databricks-warehouset. Det kräver Windows.

- Lägg användarens object ID i `gold_reader_object_ids` i `infra/envs/prod/terraform.tfvars`
  (`az ad user show --id <upn> --query id -o tsv`). Prod-deployen ger *Storage Blob Data Reader* på bara
  `gold`-containern.
- `infra/lab/` skapar en Windows-VM med Power BI Desktop (lokal state, RDP bara från angivna IP,
  avstängning 22:00). Ta bort den med `terraform destroy` när du är klar.
- Frågorna finns i [`gold_queries.pq`](gold_queries.pq): skapa parametern `StorageAccount`
  (`terraform output -raw storage_account_name`), funktionen `GoldTable` och tabellfrågorna. Logga in med
  *Organisationskonto*.

## Alternativ: via Synapse serverless

Vyerna i Synapse (`synapse/sql/20_views.sql`) finns kvar. Hämta data med *Azure Synapse Analytics SQL*
mot `terraform output -raw synapse_serverless_endpoint`, databasen `fallen_leaves`, och ge användaren
rollen `gold_reader`:

```sql
CREATE USER [namn@domän.se] FROM EXTERNAL PROVIDER;
ALTER ROLE gold_reader ADD MEMBER [namn@domän.se];
```
