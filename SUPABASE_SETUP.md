# Supabase Database Setup & Configuration

## Overview
This scraper is configured to use **Supabase (PostgreSQL)** as the primary cloud database for storing scraped business data. All scraped data is automatically synchronized to Supabase and accessible from anywhere.

## Current Configuration

### Database Connection
- **Database**: Supabase PostgreSQL (Cloud)
- **Connection String**: Configured in `.env` file
- **Behavior**: New crawled data is **added** to existing data (not replaced)
- **Deduplication**: Based on `source_url` - duplicate URLs are automatically skipped

### Environment Variables
The `.env` file contains:
```env
DATABASE_URL=postgresql://postgres.brmljayacipdhfgppuzk:scrapping-database%40123@aws-1-eu-central-1.pooler.supabase.com:5432/postgres
DIRECT_URL=postgresql://postgres.brmljayacipdhfgppuzk:scrapping-database%40123@aws-1-eu-central-1.pooler.supabase.com:5432/postgres
```

## Data Storage Strategy

### How Data is Added (Not Replaced)
The system uses PostgreSQL's `INSERT ... ON CONFLICT DO NOTHING` strategy:

```sql
INSERT INTO businesses (source_url, business_name_ar, ...)
VALUES (...)
ON CONFLICT (source_url) DO NOTHING
```

This means:
- ✅ **New businesses** are added to the database
- ✅ **Existing businesses** (same source_url) are skipped
- ✅ **No data loss** - existing records are never overwritten
- ✅ **Incremental growth** - database grows with each crawl

### Arabic Data Priority
The scraper collects and displays **Arabic business names** as the primary data:
- `business_name_ar` - Arabic business name (primary)
- `address_ar` - Arabic address
- `category_ar` - Arabic category
- English fields are used as fallback when Arabic is not available

## Streamlit App Configuration

### Database Connection Priority
The Streamlit app automatically connects to Supabase when `DATABASE_URL` is set:

```python
# Priority order:
1. DATABASE_URL environment variable (Supabase)
2. Streamlit secrets (if deployed)
3. Local SQLite fallback (data/scraper.sqlite)
```

### Visual Indicators
The app displays the current database connection:
- 🌐 **Green badge**: Connected to Supabase (Cloud)
- 💾 **Yellow badge**: Using local SQLite

### Column Display
The data table shows bilingual column headers:
- اسم الشركة (Business Name) - Arabic business names
- الهاتف (Phone)
- البريد الإلكتروني (Email)
- العنوان (Address) - Arabic addresses
- الفئة (Category) - Arabic categories

## Data Export

### CSV Downloads
Two export options are available:

1. **Download Filtered CSV**
   - Exports businesses matching current filters
   - Includes all filtered results (no 500-row limit)
   - Original column names preserved in CSV

2. **Export All Data (Unfiltered)**
   - Exports ALL businesses from database
   - No filters applied
   - May take time for large datasets

### CSV Format
Exported CSV files contain:
- `business_name_ar` - Arabic business name
- `phone` - Phone number
- `email` - Email address
- `address_ar` - Arabic address
- `category_ar` - Arabic category
- `source_url` - Original Yellow Pages URL
- `matched_facets` - Matched categories/keywords
- `scraped_at` - Timestamp of scraping

## Crawling Behavior

### Incremental Crawling
When you run a crawl:
1. System checks existing businesses by `source_url`
2. Only **new** businesses are scraped and saved
3. Existing businesses are automatically skipped
4. Database grows incrementally with each crawl

### Job Status Tracking
The system tracks crawl jobs in the `scrape_jobs` table:
- **pending** - Job queued for execution
- **running** - Currently crawling
- **done** - Completed successfully
- **failed** - Encountered errors

### Crawl Scope
You can run:
- **Scoped Crawl** - Only selected filters (keywords, cities, etc.)
- **Full Dataset Crawl** - All configured taxonomy targets

## Database Schema

### Main Tables

#### `businesses`
Stores scraped business data:
- `source_url` (UNIQUE) - Primary identifier
- `business_name_ar` - Arabic business name
- `business_name` - English business name (fallback)
- `category_ar` - Arabic category
- `address_ar` - Arabic address
- `phone`, `email`, `website`, `facebook_url`
- `scraped_at` - Timestamp

#### `scrape_jobs`
Tracks crawl job status:
- `target_type` - category/keyword/brand
- `target_slug` - Specific target identifier
- `city_slug` - City filter
- `status` - pending/running/done/failed
- `pages_scraped`, `rows_written` - Progress metrics

#### `business_facets`
Links businesses to categories/keywords:
- `source_url` - Business reference
- `facet_type` - category/keyword/brand/city/area/district
- `slug` - Facet identifier
- `name_ar` - Arabic name

## Verification

### Check Database Status
Run the status check script:
```bash
python check_db_status.py
```

This shows:
- Total businesses in Supabase
- Crawl job status breakdown
- Recent activity

### Manual Database Access
You can connect to Supabase directly using:
- **Supabase Dashboard**: https://supabase.com/dashboard
- **SQL Editor**: Run queries directly in Supabase
- **psql**: Use the connection string with PostgreSQL client

## Troubleshooting

### App Shows Local SQLite Warning
**Problem**: App displays "Using Local SQLite Database"

**Solution**:
1. Verify `.env` file exists in project root
2. Check `DATABASE_URL` is set correctly
3. Restart the Streamlit app

### No Data Showing
**Problem**: App shows "No saved businesses"

**Solution**:
1. Check database connection (green badge should show)
2. Run a crawl using "Run Scoped Crawl" button
3. Verify filters aren't too restrictive

### Duplicate Data Concerns
**Problem**: Worried about duplicate entries

**Solution**:
- System automatically prevents duplicates using `source_url`
- Each business URL can only exist once in database
- Re-running crawls is safe and won't create duplicates

## Best Practices

### Regular Crawling
- Run crawls periodically to keep data fresh
- Use scoped crawls for specific targets
- Monitor job status to catch failures

### Data Export
- Export data regularly for backup
- Use filtered exports for specific analysis
- CSV files are UTF-8 encoded for Arabic support

### Database Maintenance
- Supabase handles backups automatically
- Monitor database size in Supabase dashboard
- Consider archiving old data if needed

## Migration from SQLite to Supabase

If you have existing data in local SQLite and want to migrate:

1. **Export from SQLite**:
   ```bash
   python -c "from scraper.db import get_connection; import pandas as pd; conn = get_connection('data/scraper.sqlite'); df = pd.read_sql('SELECT * FROM businesses', conn); df.to_csv('backup.csv', index=False)"
   ```

2. **Import to Supabase**:
   - Use the Supabase dashboard's CSV import feature
   - Or use a Python script with `PostgresWriter`

3. **Verify Migration**:
   ```bash
   python check_db_status.py
   ```

## Support

For issues or questions:
1. Check this documentation
2. Review error logs in `data/crawl.log`
3. Verify Supabase connection in dashboard
4. Check environment variables are set correctly
