# Supabase Integration Summary

## Database Overview

**Project Name**: scrapping-database  
**Project ID**: brmljayacipdhfgppuzk  
**Region**: eu-central-1 (Europe - Frankfurt)  
**Status**: ACTIVE_HEALTHY  
**PostgreSQL Version**: 17.6.1.121  

## Current Database Statistics (as of 2026-05-14)

### Business Data
- **Total Businesses**: 13,232
- **With Arabic Names**: 3,584 (27.1%)
- **With Email**: 2 (0.02%)
- **With Phone**: 13,205 (99.8%)
- **Unique Categories**: 383
- **Unique Cities**: 14
- **Last Scraped**: 2026-05-14 15:26:22 UTC

### Data Quality Insights
✅ **Excellent phone coverage** (99.8%)  
⚠️ **Low email coverage** (0.02%) - Only 2 businesses have emails  
✅ **Good Arabic name coverage** (27.1%)  

### Crawl Job Status
- **Brand Jobs**: 69,902 pending
- **Category Jobs**: 77 pending, 1 failed
- **Keyword Jobs**: 106 pending, 1 running, 1 failed
- **Currently Running**: 1 keyword job (15 pages scraped, 600 rows written)

## Database Schema

### Core Tables

#### 1. `businesses` (13,232 rows)
Main table storing business information with RLS enabled.

**Columns**:
- `id` (bigint, primary key, auto-increment)
- `source_url` (text, unique) - Yellow Pages URL
- `business_name` (text) - English name
- `business_name_ar` (text) - Arabic name
- `category_slug` (text)
- `category_ar` (text) - Arabic category
- `city_slug` (text)
- `governorate_ar` (text) - Arabic governorate
- `phone` (text)
- `email` (text)
- `website` (text)
- `facebook_url` (text)
- `address` (text)
- `address_ar` (text) - Arabic address
- `raw_html_hash` (text)
- `source_tier` (integer)
- `scraped_at` (text)

#### 2. `business_facets` (60,540 rows)
Stores taxonomy associations for businesses.

**Columns**:
- `source_url` (text, FK to businesses)
- `facet_type` (text) - category, brand, keyword, city, area, district
- `slug` (text)
- `name` (text)
- `name_ar` (text) - Arabic name

**Primary Key**: (source_url, facet_type, slug)

#### 3. `categories` (720 rows)
Business category taxonomy.

**Columns**:
- `slug` (text, primary key)
- `name` (text)
- `parent_slug` (text, nullable)
- `result_count` (integer)
- `href` (text)
- `scraped_at` (text)

#### 4. `brands` (4,994 rows)
Brand taxonomy.

**Columns**:
- `slug` (text, primary key)
- `name` (text)
- `result_count` (integer)
- `href` (text)
- `scraped_at` (text)

#### 5. `keywords` (113 rows)
Keyword taxonomy (import, export, factory, etc.).

**Columns**:
- `slug` (text, primary key)
- `name` (text)
- `href` (text)
- `scraped_at` (text)

#### 6. `locations` (384 rows)
Geographic taxonomy (cities, areas, districts).

**Columns**:
- `slug` (text, primary key)
- `name` (text)
- `type` (text) - city, area, or district
- `external_id` (text)
- `parent_slug` (text, FK to locations)
- `result_count` (integer)
- `scraped_at` (text)

#### 7. `scrape_jobs` (70,088 rows)
Tracks crawl job status and progress.

**Columns**:
- `id` (bigint, primary key, auto-increment)
- `target_type` (text) - category, brand, or keyword
- `target_slug` (text)
- `category_slug` (text)
- `city_slug` (text, nullable)
- `status` (text) - pending, running, done, or failed
- `pages_scraped` (integer)
- `rows_written` (integer)
- `started_at` (timestamptz, nullable)
- `finished_at` (timestamptz, nullable)
- `error` (text)

#### 8. `schema_meta` (1 row)
Stores schema version metadata.

## Connection Details

### Environment Variables
```bash
DATABASE_URL=postgresql://postgres.brmljayacipdhfgppuzk:scrapping-database%40123@aws-1-eu-central-1.pooler.supabase.com:5432/postgres
```

### Connection String Components
- **Host**: aws-1-eu-central-1.pooler.supabase.com (Supavisor pooler)
- **Port**: 5432
- **Database**: postgres
- **User**: postgres.brmljayacipdhfgppuzk
- **Password**: scrapping-database@123 (URL encoded as %40)

### Direct Database Host
- **Direct Host**: db.brmljayacipdhfgppuzk.supabase.co
- **Note**: Use pooler for application connections, direct for admin tools

## Streamlit Integration

### Configuration Files

#### 1. `.env` (Local Development)
```env
DATABASE_URL=postgresql://postgres.brmljayacipdhfgppuzk:scrapping-database%40123@aws-1-eu-central-1.pooler.supabase.com:5432/postgres
DIRECT_URL=postgresql://postgres.brmljayacipdhfgppuzk:scrapping-database%40123@aws-1-eu-central-1.pooler.supabase.com:5432/postgres
```

#### 2. `.streamlit/secrets.toml` (Streamlit Local Testing)
```toml
DATABASE_URL = "postgresql://postgres.brmljayacipdhfgppuzk:scrapping-database%40123@aws-1-eu-central-1.pooler.supabase.com:5432/postgres"
```

#### 3. Streamlit Cloud Secrets
For deployment, add in Streamlit Cloud app settings:
```toml
DATABASE_URL = "postgresql://postgres.brmljayacipdhfgppuzk:scrapping-database%40123@aws-1-eu-central-1.pooler.supabase.com:5432/postgres"
```

### UI Features

The Streamlit app (`app/streamlit_app.py`) includes:

1. **Database Status Indicator**
   - Shows connection type (Supabase vs SQLite)
   - Real-time status updates

2. **Database Statistics Dashboard**
   - Total businesses count
   - Data quality metrics (emails, phones, Arabic names)
   - Unique categories and cities
   - Last update timestamp

3. **Data Export**
   - Filtered CSV export
   - Full database export with progress indicator
   - UTF-8 BOM encoding for Excel compatibility

4. **Real-time Crawl Monitoring**
   - Auto-refresh every 15 seconds
   - Live job status
   - Progress tracking

## Security Features

### Row Level Security (RLS)
All tables have RLS enabled:
- ✅ businesses
- ✅ business_facets
- ✅ categories
- ✅ brands
- ✅ keywords
- ✅ locations
- ✅ scrape_jobs
- ✅ schema_meta

### Foreign Key Constraints
- `business_facets.source_url` → `businesses.source_url`
- `locations.parent_slug` → `locations.slug`

### Data Validation
- `locations.type` must be: city, area, or district
- `business_facets.facet_type` must be: category, brand, keyword, city, area, or district
- `scrape_jobs.target_type` must be: category, brand, or keyword
- `scrape_jobs.status` must be: pending, running, done, or failed

## Performance Optimizations

### Indexes
- Primary keys on all tables
- Unique constraint on `businesses.source_url`
- Composite primary key on `business_facets` (source_url, facet_type, slug)

### Connection Pooling
- Using Supavisor pooler for efficient connection management
- Recommended for serverless/cloud deployments

### Query Optimizations
- Batch facet loading to avoid N+1 queries
- Indexed lookups on frequently queried columns
- Result limits to prevent memory issues

## Common Queries

### Get Business Statistics
```sql
SELECT 
  COUNT(*) as total_businesses,
  COUNT(CASE WHEN business_name_ar IS NOT NULL AND business_name_ar != '' THEN 1 END) as with_arabic_names,
  COUNT(CASE WHEN email IS NOT NULL AND email != '' THEN 1 END) as with_email,
  COUNT(CASE WHEN phone IS NOT NULL AND phone != '' THEN 1 END) as with_phone,
  COUNT(DISTINCT category_slug) as unique_categories,
  COUNT(DISTINCT city_slug) as unique_cities
FROM businesses;
```

### Get Crawl Job Summary
```sql
SELECT 
  target_type,
  status,
  COUNT(*) as job_count,
  SUM(pages_scraped) as total_pages,
  SUM(rows_written) as total_rows
FROM scrape_jobs
GROUP BY target_type, status
ORDER BY target_type, status;
```

### Find Businesses with Emails
```sql
SELECT 
  business_name_ar,
  business_name,
  email,
  phone,
  city_slug
FROM businesses
WHERE email IS NOT NULL AND email != ''
ORDER BY scraped_at DESC;
```

### Get Top Categories by Business Count
```sql
SELECT 
  bf.slug,
  bf.name,
  bf.name_ar,
  COUNT(DISTINCT bf.source_url) as business_count
FROM business_facets bf
WHERE bf.facet_type = 'category'
GROUP BY bf.slug, bf.name, bf.name_ar
ORDER BY business_count DESC
LIMIT 20;
```

### Get Recent Crawl Activity
```sql
SELECT 
  target_type,
  target_slug,
  city_slug,
  status,
  pages_scraped,
  rows_written,
  started_at,
  finished_at
FROM scrape_jobs
WHERE started_at IS NOT NULL
ORDER BY started_at DESC
LIMIT 50;
```

## Maintenance Tasks

### Check Database Size
```sql
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Find Duplicate Businesses
```sql
SELECT 
  source_url,
  COUNT(*) as count
FROM businesses
GROUP BY source_url
HAVING COUNT(*) > 1;
```

### Clean Failed Jobs (if needed)
```sql
-- Reset failed jobs to pending for retry
UPDATE scrape_jobs
SET status = 'pending',
    error = '',
    started_at = NULL,
    finished_at = NULL
WHERE status = 'failed';
```

### Archive Old Crawl Jobs
```sql
-- Delete completed jobs older than 30 days
DELETE FROM scrape_jobs
WHERE status = 'done'
  AND finished_at < NOW() - INTERVAL '30 days';
```

## Backup and Recovery

### Export Data
```bash
# Using Supabase CLI
supabase db dump -f backup.sql

# Or using pg_dump
pg_dump "postgresql://postgres.brmljayacipdhfgppuzk:scrapping-database@123@aws-1-eu-central-1.pooler.supabase.com:5432/postgres" > backup.sql
```

### Export to CSV
```sql
-- Export businesses to CSV
COPY (
  SELECT * FROM businesses
) TO '/tmp/businesses.csv' WITH CSV HEADER;
```

### Restore from Backup
```bash
# Using Supabase CLI
supabase db reset --db-url "postgresql://..."

# Or using psql
psql "postgresql://..." < backup.sql
```

## Monitoring and Alerts

### Key Metrics to Monitor
1. **Database Size**: Track growth over time
2. **Connection Count**: Monitor pooler usage
3. **Query Performance**: Identify slow queries
4. **Failed Jobs**: Alert on high failure rates
5. **Data Quality**: Track email/phone coverage trends

### Supabase Dashboard
Access at: https://supabase.com/dashboard/project/brmljayacipdhfgppuzk

Monitor:
- Database health
- API usage
- Storage usage
- Real-time connections
- Logs and errors

## Troubleshooting

### Connection Issues
```bash
# Test connection
python verify_setup.py

# Check if DATABASE_URL is set
echo $DATABASE_URL
```

### Slow Queries
```sql
-- Find slow queries
SELECT 
  query,
  calls,
  total_time,
  mean_time,
  max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

### RLS Policy Issues
```sql
-- Check RLS policies
SELECT 
  schemaname,
  tablename,
  policyname,
  permissive,
  roles,
  cmd,
  qual
FROM pg_policies
WHERE schemaname = 'public';
```

## Next Steps

1. ✅ Database is connected and operational
2. ✅ Streamlit UI is integrated with Supabase
3. ✅ Data export functionality is working
4. 🔄 Consider adding indexes for frequently filtered columns
5. 🔄 Set up automated backups
6. 🔄 Monitor database growth and performance
7. 🔄 Implement data quality improvements (email collection)
8. 🔄 Deploy to Streamlit Cloud with DATABASE_URL secret

## Support Resources

- **Supabase Documentation**: https://supabase.com/docs
- **Supabase Dashboard**: https://supabase.com/dashboard/project/brmljayacipdhfgppuzk
- **PostgreSQL Documentation**: https://www.postgresql.org/docs/17/
- **Project Verification**: Run `python verify_setup.py`
