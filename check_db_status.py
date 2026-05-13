"""Check Supabase DB summary."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from scraper.postgres_db import get_connection

DATABASE_URL = "postgresql://postgres.brmljayacipdhfgppuzk:scrapping-database%40123@aws-1-eu-central-1.pooler.supabase.com:5432/postgres"
conn = get_connection(DATABASE_URL)

row = conn.execute("SELECT COUNT(*) AS cnt FROM businesses").fetchone()
print(f"Total businesses in Supabase: {row['cnt']}")

rows = conn.execute("SELECT status, COUNT(*) AS cnt FROM scrape_jobs GROUP BY status ORDER BY status").fetchall()
print("\nAll scrape jobs by status:")
for r in rows:
    print(f"  {r['status']}: {r['cnt']}")

rows = conn.execute("SELECT target_type, COUNT(*) AS cnt FROM scrape_jobs GROUP BY target_type ORDER BY target_type").fetchall()
print("\nAll scrape jobs by type:")
for r in rows:
    print(f"  {r['target_type']}: {r['cnt']}")

# Show specifically done/failed for our targets
GAP_TARGETS = ['factory', 'import', 'export', 'distribution', 'import-&-export',
               'factory-equipment-and-supplies',
               '\u0645\u0635\u0646\u0639', '\u0627\u0633\u062a\u064a\u0631\u0627\u062f', '\u062a\u0635\u062f\u064a\u0631', '\u062a\u0648\u0632\u064a\u0639', '\u0627\u0633\u062a\u064a\u0631\u0627\u062f \u0648\u062a\u0635\u062f\u064a\u0631']
rows = conn.execute("""
    SELECT target_slug, target_type, status, SUM(rows_written) AS total_rows, COUNT(*) AS job_count
    FROM scrape_jobs
    WHERE target_slug = ANY(%s)
    GROUP BY target_slug, target_type, status
    ORDER BY target_slug, status
""", (GAP_TARGETS,)).fetchall()
print("\nGap target jobs:")
for r in rows:
    print(f"  [{r['target_type']}] {r['target_slug']}: {r['status']} x{r['job_count']} jobs - {r['total_rows']} rows")

conn.close()
