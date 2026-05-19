"""Run focused crawl for specific keywords and cities, then export to CSV."""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add src to path
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scraper.config import Settings
from scraper.mass_crawl import run_mass_crawl
from scraper.storage import open_connection, is_postgres_url
import pandas as pd

# Keywords from the screenshot (Arabic)
KEYWORDS = [
    "استيراد",           # Import
    "استيراد وتصدير",    # Import & Export
    "تصدير",            # Export
    "توزيع",            # Distribution
    "مصنع",             # Factory
]

# Cities from the screenshot
CITIES = [
    "alexandria",
    "cairo",
    "giza",
]

def export_to_csv(db_path: str, output_file: str):
    """Export all scraped data to CSV."""
    print("\n" + "="*60)
    print("EXPORTING DATA TO CSV")
    print("="*60)
    
    conn, backend = open_connection(db_path)
    
    try:
        # Query to get all businesses with Arabic names prioritized
        # Fixed: Use city_slug (from facets) instead of governorate_ar (from scraped page)
        query = """
        SELECT 
            COALESCE(NULLIF(b.business_name_ar, ''), b.business_name) AS business_name,
            COALESCE(NULLIF(b.category_ar, ''), b.category_slug) AS category,
            b.city_slug AS city,
            COALESCE(NULLIF(b.address_ar, ''), b.address) AS address,
            b.phone,
            b.email,
            b.website,
            b.facebook_url,
            b.source_url,
            b.scraped_at
        FROM businesses b
        ORDER BY b.scraped_at DESC
        """
        
        print(f"Loading data from {backend} database...")
        rows = conn.execute(query).fetchall()
        
        if not rows:
            print("❌ No data found in database")
            return False
        
        # Convert to DataFrame
        df = pd.DataFrame([dict(row) for row in rows])
        
        # Remove duplicates based on source_url
        df_unique = df.drop_duplicates(subset=['source_url'])
        
        print(f"✅ Loaded {len(df):,} records")
        print(f"✅ Unique businesses: {len(df_unique):,}")
        
        # Count Arabic vs English names
        arabic_count = df_unique['business_name'].str.contains('[\u0600-\u06FF]', regex=True, na=False).sum()
        print(f"📊 Businesses with Arabic names: {arabic_count:,}")
        print(f"📊 Businesses with English names: {len(df_unique) - arabic_count:,}")
        
        # Export to CSV with UTF-8 BOM for Excel compatibility
        df_unique.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print(f"\n✅ Data exported to: {output_file}")
        print(f"📁 File size: {Path(output_file).stat().st_size / 1024 / 1024:.2f} MB")
        
        return True
        
    finally:
        conn.close()


def main():
    print("="*60)
    print("FOCUSED CRAWL: KEYWORDS + ALL CITIES")
    print("="*60)
    
    cfg = Settings()
    
    # Determine which database to use
    db_path = cfg.database_url or cfg.db_path
    is_supabase = is_postgres_url(db_path)
    
    print(f"\n📊 Target Keywords:")
    for kw in KEYWORDS:
        print(f"   - {kw}")
    
    print(f"\n🌍 Target Cities:")
    for city in CITIES:
        print(f"   - {city}")
    
    print(f"\n💾 Database: {'Supabase (Cloud)' if is_supabase else 'Local SQLite'}")
    print(f"📁 Path: {str(db_path)[:60]}...")
    
    # Prepare output filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = ROOT / "output"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"yp_egypt_focused_crawl_{timestamp}.csv"
    
    print(f"\n📄 Output CSV: {output_file}")
    
    print("\n" + "="*60)
    print("🚀 STARTING BACKGROUND CRAWL")
    print("="*60)
    print("The crawl will:")
    print("1. Scrape businesses for the selected keywords")
    print("2. Cover all selected cities (Alexandria, Cairo, Giza)")
    print("3. Save data to Supabase (new data only, no duplicates)")
    print("4. Export all data to CSV when complete")
    print("\n⏳ This may take 30-60 minutes depending on data volume...")
    print("="*60)
    
    try:
        # Run the mass crawl with specific keywords and cities
        # The keywords will be expanded to include English equivalents automatically
        rows_written = run_mass_crawl(
            db_path=db_path,
            max_pages=cfg.mass_crawl_max_pages,
            headless=True,
            target_types=["keyword"],
            target_slugs_by_type={"keyword": KEYWORDS},
            cities="none",  # We'll specify cities explicitly
            city_slugs=CITIES,
        )
        
        print("\n" + "="*60)
        print("CRAWL COMPLETE")
        print("="*60)
        print(f"✅ New businesses scraped: {rows_written:,}")
        
        # Export to CSV
        if export_to_csv(db_path, str(output_file)):
            print("\n✅ SUCCESS! Data exported to CSV")
            print(f"\n📂 Open file: {output_file}")
        else:
            print("\n⚠️  Crawl completed but no data to export")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Crawl interrupted by user")
        print("Partial data may have been saved to database")
        
        # Try to export whatever we have
        print("\nAttempting to export existing data...")
        export_to_csv(db_path, str(output_file))
        
    except Exception as e:
        print(f"\n\n❌ ERROR during crawl: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to export whatever we have
        print("\nAttempting to export existing data...")
        try:
            export_to_csv(db_path, str(output_file))
        except:
            pass


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
    
    main()
