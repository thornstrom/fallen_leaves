-- Körs mot master på serverless-endpointen.
IF DB_ID('fallen_leaves') IS NULL
    CREATE DATABASE fallen_leaves COLLATE Latin1_General_100_BIN2_UTF8;
GO
