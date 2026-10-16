-- Körs mot databasen fallen_leaves. Vyer över gold-tabellerna (Delta) som Databricks skriver.

CREATE OR ALTER VIEW dbo.daily_station_delay_weather AS
SELECT *
FROM OPENROWSET(
    BULK 'daily_station_delay_weather/',
    DATA_SOURCE = 'gold',
    FORMAT = 'DELTA'
) AS r;
GO

CREATE OR ALTER VIEW dbo.daily_national AS
SELECT *
FROM OPENROWSET(
    BULK 'daily_national/',
    DATA_SOURCE = 'gold',
    FORMAT = 'DELTA'
) AS r;
GO

CREATE OR ALTER VIEW dbo.correlation_results AS
SELECT *
FROM OPENROWSET(
    BULK 'correlation_results/',
    DATA_SOURCE = 'gold',
    FORMAT = 'DELTA'
) AS r;
GO

-- Bara höstmånaderna (september–november), som är projektets fråga.
CREATE OR ALTER VIEW dbo.daily_national_autumn AS
SELECT *
FROM dbo.daily_national
WHERE MONTH(event_date) IN (9, 10, 11);
GO
