"""Check the progress of the running crawl."""

import sys
import os
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scraper.config import Settings
from scraper.storage import open_connection, is_postgres_url

def main():
    print("="*60)
    print("CRAWL PROGRESS CHECK")
    print("="*60)
    
    cfg = Settings()
    db_path = cfg.database_url or cfg.db_path
    is_supabase = is_postgres_url(db_path)
    
    print(f"\n💾 Database: {'Supabase (Cloud)' if is_supabase else 'Local SQLite'}")
    
    conn, backend = open_connection(db_path)
    
    try:
        # Get job summary
        print("\n📊 CRAWL JOBS STATUS")
        print("-"*60)
        
        rows = conn.execute("""
            SELECT status, COUNT(*) as jobs,
                   SUM(pages_scraped) as pages,
                   SUM(rows_written) as rows
            FROM scrape_jobs
            GROUP BY status
            ORDER BY status
        """).fetchall()
        
        total_jobs = 0
        total_pages = 0
        total_rows = 0
        
        for row in rows:
            status = row['status']
            jobs = row['jobs']
            pages = row['pages'] or 0
            rows_count = row['rows'] or 0
            
            total_jobs += jobs
            total_pages += pages
            total_rows += rows_count
            
            emoji = {
                'pending': '⏳',
                'running': '🔄',
                'done': '✅',
                'failed': '❌'
            }.get(status, '❓')
            
            print(f"{emoji} {status.upper():8} {jobs:5,} jobs | {pages:6,} pages | {rows_count:6,} rows")
        
        print("-"*60)
        print(f"   TOTAL:    {total_jobs:5,} jobs | {total_pages:6,} pages | {total_rows:6,} rows")
        
        # Get total businesses
        print("\n📈 DATABASE STATISTICS")
        print("-"*60)
        
        result = conn.execute("SELECT COUNT(*) as cnt FROM businesses").fetchone()
        total_businesses = result['cnt']
        
        result = conn.execute("""
            SELECT COUNT(*) as cnt FROM businesses
            WHERE business_name_ar IS NOT NULL AND business_name_ar != ''
        """).fetchone()
        arabic_businesses = result['cnt']
        
        result = conn.execute("""
            SELECT COUNT(*) as cnt FROM businesses
            WHERE scraped_at > datetime('now', '-1 hour')
        """ if backend == 'sqlite' else """
            SELECT COUNT(*) as cnt FROM businesses
            WHERE scraped_at::timestamp > now() - interval '1 hour'
        """).fetchone()
        recent_businesses = result['cnt']
        
        print(f"Total businesses:        {total_businesses:8,}")
        print(f"With Arabic names:       {arabic_businesses:8,} ({arabic_businesses/max(total_businesses,1)*100:.1f}%)")
        print(f"Added in last hour:      {recent_businesses:8,}")
        
        # Get currently running jobs
        running_jobs = conn.execute("""
            SELECT target_type, target_slug, city_slug, pages_scraped, rows_written
            FROM scrape_jobs
            WHERE status = 'running'
            ORDER BY started_at DESC
            LIMIT 5
        """).fetchall()
        
        if running_jobs:
            print("\n🔄 CURRENTLY RUNNING JOBS")
            print("-"*60)
            for job in running_jobs:
                target = f"{job['target_type']}: {job['target_slug']}"
                city = job['city_slug'] or 'all cities'
                pages = job['pages_scraped'] or 0
                rows = job['rows_written'] or 0
                print(f"  {target:30} | {city:15} | {pages:3} pages | {rows:4} rows")
        
        # Estimate completion
        job_rows = conn.execute("""
            SELECT status, COUNT(*) as jobs
            FROM scrape_jobs
            GROUP BY status
        """).fetchall()
        
        pending = sum(row['jobs'] for row in job_rows if row['status'] == 'pending')
        running = sum(row['jobs'] for row in job_rows if row['status'] == 'running')
        done = sum(row['jobs'] for row in job_rows if row['status'] == 'done')
        
        if total_jobs > 0:
            progress = (done / total_jobs) * 100
            print(f"\n📊 OVERALL PROGRESS")
            print("-"*60)
            print(f"Progress: {progress:.1f}% ({done}/{total_jobs} jobs completed)")
            
            if running > 0 or pending > 0:
                print(f"Status: 🔄 CRAWLING IN PROGRESS")
                print(f"Remaining: {pending + running} jobs")
            else:
                print(f"Status: ✅ CRAWL COMPLETE")
        
        print("\n" + "="*60)
        
    finally:
        conn.close()


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
    
    main()
