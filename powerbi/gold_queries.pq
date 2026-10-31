// Power Query-frågor som läser gold-tabellerna (Delta) direkt från ADLS Gen2.
// Klistra in varje fråga i Power BI Desktop: Hämta data → Tom fråga → Avancerad redigerare,
// och döp frågan till namnet i rubriken. Inloggning: Organisationskonto (OAuth/Entra ID),
// eftersom storage-kontot saknar nycklar.

// --- Parameter: StorageAccount (Hantera parametrar → Ny, typ Text) -----------------------
// Värde: terraform output -raw storage_account_name   (i infra/envs/prod)
"stflprodxxxxx" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]

// --- Funktion: GoldTable ----------------------------------------------------------------
// Läser en Delta-tabell under gold/delta/<tabell>/. HierarchicalNavigation = false ger en
// platt fillista, vilket är vad DeltaLake.Table förväntar sig.
(table as text) as table =>
let
    Files = AzureStorage.DataLake(
        "https://" & StorageAccount & ".dfs.core.windows.net/gold/delta/" & table,
        [HierarchicalNavigation = false]
    ),
    Delta = DeltaLake.Table(Files)
in
    Delta

// --- daily_national ---------------------------------------------------------------------
let
    Source = GoldTable("daily_national")
in
    Source

// --- daily_national_autumn (samma som Synapse-vyn: september–november) ------------------
let
    Source = GoldTable("daily_national"),
    Autumn = Table.SelectRows(Source, each List.Contains({9, 10, 11}, Date.Month([event_date])))
in
    Autumn

// --- daily_station_delay_weather --------------------------------------------------------
let
    Source = GoldTable("daily_station_delay_weather")
in
    Source

// --- correlation_results ----------------------------------------------------------------
let
    Source = GoldTable("correlation_results")
in
    Source
