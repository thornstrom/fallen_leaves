-- Körs mot databasen fallen_leaves.
-- Variabler (sqlcmd -v): gold_root, master_key_password
--
-- Synapse läser gold med sin managed identity, så att Power BI-användare inte behöver
-- behörighet direkt på data lake.

IF NOT EXISTS (SELECT 1 FROM sys.symmetric_keys WHERE name = '##MS_DatabaseMasterKey##')
    CREATE MASTER KEY ENCRYPTION BY PASSWORD = '$(master_key_password)';
GO

IF NOT EXISTS (SELECT 1 FROM sys.database_scoped_credentials WHERE name = 'WorkspaceIdentity')
    CREATE DATABASE SCOPED CREDENTIAL WorkspaceIdentity WITH IDENTITY = 'Managed Identity';
GO

IF NOT EXISTS (SELECT 1 FROM sys.external_data_sources WHERE name = 'gold')
    CREATE EXTERNAL DATA SOURCE gold WITH (
        LOCATION = '$(gold_root)',
        CREDENTIAL = WorkspaceIdentity
    );
GO

-- Läsroll för rapportanvändare. Lägg till användare med:
--   CREATE USER [namn@domän] FROM EXTERNAL PROVIDER;
--   ALTER ROLE gold_reader ADD MEMBER [namn@domän];
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'gold_reader' AND type = 'R')
    CREATE ROLE gold_reader;
GO

GRANT SELECT ON SCHEMA::dbo TO gold_reader;
GRANT REFERENCES ON DATABASE SCOPED CREDENTIAL::WorkspaceIdentity TO gold_reader;
GO
