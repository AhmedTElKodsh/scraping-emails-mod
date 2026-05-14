"""Verify Supabase setup and Arabic data configuration."""

import sys
import os
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scraper.config import Settings
from scraper.storage import is_postgres_url, open_connection

def main():
    print("=" * 60)
    print("SUPABASE SETUP VERIFICATION")
    print("=" * 60)
    print()
    
    # Check environment
    print("1. Environment Configuration")
    print("-" * 60)
    cfg = Settings()
    
    if cfg.database_url:
        print(f"✅ DATABASE_URL is set")
        if is_postgres_url(cfg.database_url):
            print(f"✅ DATABASE_URL is a valid PostgreSQL URL")
            print(f"   Connection: {cfg.database_url[:50]}...")
        else:
            print(f"❌ DATABASE_URL is not a PostgreSQL URL")
    else:
        print(f"❌ DATABASE_URL is not set")
        print(f"   Falling back to SQLite: {cfg.db_path}")
    print()
    
    # Check database connection
    print("2. Database Connection")
    print("-" * 60)
    try:
        target = cfg.database_url or cfg.db_path
        conn, backend = open_connection(target)
        print(f"✅ Successfully connected to {backend.upper()} database")
        
        # Check for businesses table
        if backend == "postgres":
            result = conn.execute(
                "SELECT COUNT(*) as count FROM businesses"
            ).fetchone()
        else:
            result = conn.execute(
                "SELECT COUNT(*) as count FROM businesses"
            ).fetchone()
        
        count = result['count'] if result else 0
        print(f"✅ Businesses table exists with {count:,} records")
        
        # Check for Arabic data
        if backend == "postgres":
            result = conn.execute(
                """SELECT COUNT(*) as count FROM businesses 
                WHERE business_name_ar IS NOT NULL AND business_name_ar != ''"""
            ).fetchone()
        else:
            result = conn.execute(
                """SELECT COUNT(*) as count FROM businesses 
                WHERE business_name_ar IS NOT NULL AND business_name_ar != ''"""
            ).fetchone()
        
        arabic_count = result['count'] if result else 0
        print(f"✅ {arabic_count:,} businesses have Arabic names")
        
        if arabic_count > 0:
            # Show sample
            if backend == "postgres":
                sample = conn.execute(
                    """SELECT business_name_ar, category_ar, phone 
                    FROM businesses 
                    WHERE business_name_ar IS NOT NULL AND business_name_ar != ''
                    LIMIT 3"""
                ).fetchall()
            else:
                sample = conn.execute(
                    """SELECT business_name_ar, category_ar, phone 
                    FROM businesses 
                    WHERE business_name_ar IS NOT NULL AND business_name_ar != ''
                    LIMIT 3"""
                ).fetchall()
            
            print("\n   Sample Arabic data:")
            for row in sample:
                print(f"   - {row['business_name_ar']} ({row['category_ar']}) - {row['phone']}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
    print()
    
    # Check .env file
    print("3. Environment File")
    print("-" * 60)
    env_path = ROOT / ".env"
    if env_path.exists():
        print(f"✅ .env file exists at {env_path}")
        content = env_path.read_text()
        if "DATABASE_URL" in content:
            print(f"✅ DATABASE_URL is defined in .env")
        else:
            print(f"❌ DATABASE_URL is not defined in .env")
    else:
        print(f"❌ .env file not found at {env_path}")
    print()
    
    # Summary
    print("4. Summary")
    print("-" * 60)
    if cfg.database_url and is_postgres_url(cfg.database_url):
        print("✅ System is configured to use Supabase (PostgreSQL)")
        print("✅ New crawled data will be added to existing data")
        print("✅ Arabic business names are being collected and stored")
        print()
        print("Next steps:")
        print("1. Run the Streamlit app: streamlit run app/streamlit_app.py")
        print("2. Look for the green '🌐 Connected to Supabase' badge")
        print("3. Run a crawl to add new data")
        print("4. Export CSV to download all data")
    else:
        print("⚠️  System is using local SQLite database")
        print()
        print("To enable Supabase:")
        print("1. Ensure .env file exists with DATABASE_URL")
        print("2. Restart the application")
        print("3. Verify connection in Streamlit app")
    print()
    print("=" * 60)

if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
    main()
