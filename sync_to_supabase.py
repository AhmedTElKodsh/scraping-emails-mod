"""Sync local SQLite database to Supabase PostgreSQL."""

import sys
import os
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scraper.config import Settings
from scraper.db import get_connection as get_sqlite_connection
from scraper.postgres_db import get_connection as get_postgres_connection, init_db
from scraper.storage import is_postgres_url

def sync_businesses(sqlite_conn, postgres_conn):
    """Sync businesses from SQLite to PostgreSQL."""
    print("\n" + "="*60)
    print("SYNCING BUSINESSES")
    print("="*60)
    
    # Get all businesses from SQLite
    sqlite_rows = sqlite_conn.execute("""
        SELECT source_url, business_name, business_name_ar, category_slug, category_ar,
               city_slug, governorate_ar, phone, email, website, facebook_url,
               address, address_ar, raw_html_hash, source_tier, scraped_at
        FROM businesses
        ORDER BY scraped_at DESC
    """).fetchall()
    
    total = len(sqlite_rows)
    print(f"Found {total:,} businesses in local SQLite database")
    
    if total == 0:
        print("No businesses to sync")
        return 0
    
    # Check how many already exist in Supabase
    existing_urls = set()
    postgres_rows = postgres_conn.execute("SELECT source_url FROM businesses").fetchall()
    for row in postgres_rows:
        existing_urls.add(row['source_url'])
    
    print(f"Found {len(existing_urls):,} businesses already in Supabase")
    
    # Insert new businesses
    inserted = 0
    skipped = 0
    errors = 0
    
    for i, row in enumerate(sqlite_rows, 1):
        if i % 100 == 0:
            print(f"Progress: {i:,}/{total:,} ({i/total*100:.1f}%)")
        
        if row['source_url'] in existing_urls:
            skipped += 1
            continue
        
        try:
            postgres_conn.execute("""
                INSERT INTO businesses
                (source_url, business_name, business_name_ar, category_slug, category_ar,
                 city_slug, governorate_ar, phone, email, website, facebook_url,
                 address, address_ar, raw_html_hash, source_tier, scraped_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_url) DO NOTHING
            """, (
                row['source_url'],
                row['business_name'],
                row['business_name_ar'],
                row['category_slug'],
                row['category_ar'],
                row['city_slug'],
                row['governorate_ar'],
                row['phone'],
                row['email'],
                row['website'],
                row['facebook_url'],
                row['address'],
                row['address_ar'],
                row['raw_html_hash'],
                row['source_tier'],
                row['scraped_at'],
            ))
            inserted += 1
            
            if inserted % 100 == 0:
                postgres_conn.commit()
                
        except Exception as e:
            errors += 1
            if errors <= 5:  # Only print first 5 errors
                print(f"Error inserting {row['source_url']}: {e}")
    
    postgres_conn.commit()
    
    print(f"\n✅ Inserted: {inserted:,} new businesses")
    print(f"⏭️  Skipped: {skipped:,} (already exist)")
    if errors > 0:
        print(f"❌ Errors: {errors:,}")
    
    return inserted


def sync_business_facets(sqlite_conn, postgres_conn):
    """Sync business facets from SQLite to PostgreSQL."""
    print("\n" + "="*60)
    print("SYNCING BUSINESS FACETS")
    print("="*60)
    
    # Get all facets from SQLite
    sqlite_rows = sqlite_conn.execute("""
        SELECT source_url, facet_type, slug, name, name_ar
        FROM business_facets
        ORDER BY source_url
    """).fetchall()
    
    total = len(sqlite_rows)
    print(f"Found {total:,} business facets in local SQLite database")
    
    if total == 0:
        print("No facets to sync")
        return 0
    
    # Insert facets
    inserted = 0
    skipped = 0
    errors = 0
    
    for i, row in enumerate(sqlite_rows, 1):
        if i % 500 == 0:
            print(f"Progress: {i:,}/{total:,} ({i/total*100:.1f}%)")
        
        try:
            cursor = postgres_conn.execute("""
                INSERT INTO business_facets
                (source_url, facet_type, slug, name, name_ar)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (source_url, facet_type, slug) DO UPDATE SET
                    name=COALESCE(NULLIF(EXCLUDED.name, ''), business_facets.name),
                    name_ar=COALESCE(NULLIF(EXCLUDED.name_ar, ''), business_facets.name_ar)
            """, (
                row['source_url'],
                row['facet_type'],
                row['slug'],
                row['name'],
                row['name_ar'],
            ))
            
            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
            
            if inserted % 500 == 0:
                postgres_conn.commit()
                
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"Error inserting facet: {e}")
    
    postgres_conn.commit()
    
    print(f"\n✅ Inserted/Updated: {inserted:,} facets")
    print(f"⏭️  Skipped: {skipped:,}")
    if errors > 0:
        print(f"❌ Errors: {errors:,}")
    
    return inserted


def main():
    print("="*60)
    print("SYNC LOCAL SQLITE TO SUPABASE")
    print("="*60)
    
    # Load configuration
    cfg = Settings()
    
    if not cfg.database_url:
        print("❌ ERROR: DATABASE_URL not set in .env file")
        print("Please set DATABASE_URL to your Supabase connection string")
        return
    
    if not is_postgres_url(cfg.database_url):
        print("❌ ERROR: DATABASE_URL is not a PostgreSQL URL")
        return
    
    print(f"\n📁 Local SQLite: {cfg.db_path}")
    print(f"🌐 Supabase: {cfg.database_url[:50]}...")
    
    # Check if local database exists
    if not Path(cfg.db_path).exists():
        print(f"\n❌ ERROR: Local database not found at {cfg.db_path}")
        return
    
    # Connect to both databases
    print("\n🔌 Connecting to databases...")
    sqlite_conn = get_sqlite_connection(cfg.db_path)
    postgres_conn = get_postgres_connection(cfg.database_url)
    
    # Initialize Supabase schema
    print("🔧 Initializing Supabase schema...")
    init_db(postgres_conn)
    
    try:
        # Sync businesses
        businesses_synced = sync_businesses(sqlite_conn, postgres_conn)
        
        # Sync facets
        facets_synced = sync_business_facets(sqlite_conn, postgres_conn)
        
        # Final summary
        print("\n" + "="*60)
        print("SYNC COMPLETE")
        print("="*60)
        print(f"✅ {businesses_synced:,} new businesses synced to Supabase")
        print(f"✅ {facets_synced:,} facets synced to Supabase")
        
        # Show final counts
        final_count = postgres_conn.execute("SELECT COUNT(*) as cnt FROM businesses").fetchone()
        arabic_count = postgres_conn.execute(
            "SELECT COUNT(*) as cnt FROM businesses WHERE business_name_ar IS NOT NULL AND business_name_ar != ''"
        ).fetchone()
        
        print(f"\n📊 Total businesses in Supabase: {final_count['cnt']:,}")
        print(f"📊 Businesses with Arabic names: {arabic_count['cnt']:,}")
        
    finally:
        sqlite_conn.close()
        postgres_conn.close()
    
    print("\n✅ Sync completed successfully!")
    print("\nNext steps:")
    print("1. Run: streamlit run app/streamlit_app.py")
    print("2. Look for the green '🌐 Connected to Supabase' badge")
    print("3. Verify Arabic business names are displayed")


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Sync interrupted by user")
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
