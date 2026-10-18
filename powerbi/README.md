# Power BI-rapport

> **Används inte.** Projektet visualiserar i Databricks-dashboarden *Fallande löv*
> (se README steg 7). Den här guiden finns kvar som alternativ om du vill bygga en
> Power BI-rapport mot Synapse-vyerna, vilket kräver Windows och ett jobb- eller skolkonto.

Rapporten läser vyerna i Synapse serverless (`fallen_leaves`-databasen). Spara den som
**Power BI-projekt (.pbip)** i den här mappen så versionshanteras modell och rapport i git
(File → Save as → Power BI Project; aktivera först *Power BI Project (.pbip) save option*
under Options → Preview features).

## Bygg rapporten

1. **Hämta data** → *Azure Synapse Analytics SQL*.
   - Server: `terraform output -raw synapse_serverless_endpoint` (i `infra/envs/prod`)
   - Databas: `fallen_leaves`
   - Läge: **DirectQuery** (data uppdateras varje natt) eller Import med schemalagd uppdatering.
   - Inloggning: *Microsoft account* (Entra ID).
2. Välj vyerna `daily_national`, `daily_national_autumn`, `daily_station_delay_weather`, `correlation_results`.
3. Lägg till måtten i [`measures.dax`](measures.dax).
4. Sidor:

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

## Publicera och koppla till Synapse

1. Publicera till ett Power BI-workspace.
2. I Synapse Studio: **Manage → Linked services → New → Power BI** och välj workspacet.
   Då syns rapporten under *Develop → Power BI* i Synapse. (Terraforms azurerm-provider
   stöder inte den här kopplingen, så den görs manuellt en gång per miljö.)
3. Ge rapportanvändare läsrätt i Synapse:
   ```sql
   -- mot databasen fallen_leaves
   CREATE USER [namn@domän.se] FROM EXTERNAL PROVIDER;
   ALTER ROLE gold_reader ADD MEMBER [namn@domän.se];
   ```
