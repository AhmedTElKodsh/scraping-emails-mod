# Streamlit Cloud Persistence

The Streamlit app can use a persistent Supabase Postgres database by setting
`DATABASE_URL`. When this value is present, the UI and crawler use Postgres
instead of the local `data/scraper.sqlite` file.

## Supabase Setup

1. Create or choose a Supabase project.
2. In Supabase, copy the Postgres connection string from the database connection
   settings. Prefer the Supavisor session pooler connection string for hosted
   app runtimes unless your network supports the direct IPv6 database endpoint.
3. In Streamlit Community Cloud, open the app settings and add this secret:

```toml
DATABASE_URL = "postgresql://postgres.[PROJECT-REF]:[PASSWORD]@[REGION].pooler.supabase.com:5432/postgres"
```

Do not commit `.streamlit/secrets.toml` with real credentials.

## Migrate Existing Local Data

Run this once from a machine that has the local SQLite database and network
access to Supabase:

```powershell
$env:DATABASE_URL = "postgresql://postgres.[PROJECT-REF]:[PASSWORD]@[REGION].pooler.supabase.com:5432/postgres"
$env:PYTHONPATH = "src"
python -m scraper.migrate_to_postgres --sqlite-path data/scraper.sqlite
```

The migration creates the Postgres schema if needed and skips rows that already
exist by natural keys like `source_url`, `slug`, and crawl target/city.

## Runtime Notes

- `data/scraper.sqlite` remains useful for local development, but it is ignored
  by Git and is not deployed to Streamlit Cloud.
- The deployed app seeds starter taxonomy into an empty Postgres database so the
  UI is never blank on first launch.
- Brands and keywords become fully useful after the migrated database or a live
  crawl has populated brand and keyword taxonomy/facets in Postgres.
