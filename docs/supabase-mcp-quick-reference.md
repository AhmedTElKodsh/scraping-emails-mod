# Supabase MCP Quick Reference

## Project Information

**Project ID**: `brmljayacipdhfgppuzk`  
**Project Name**: scrapping-database  
**Region**: eu-central-1  

## Common MCP Commands

### 1. List All Tables
```
Use Supabase MCP tool: list_tables
Parameters:
- project_id: brmljayacipdhfgppuzk
- schemas: ["public"]
- verbose: true (for detailed column info)
```

### 2. Execute SQL Query
```
Use Supabase MCP tool: execute_sql
Parameters:
- project_id: brmljayacipdhfgppuzk
- query: "YOUR SQL QUERY HERE"
```

### 3. Get Database Statistics
```sql
SELECT 
  COUNT(*) as total_businesses,
  COUNT(CASE WHEN business_name_ar IS NOT NULL AND business_name_ar != '' THEN 1 END) as with_arabic_names,
  COUNT(CASE WHEN email IS NOT NULL AND email != '' THEN 1 END) as with_email,
  COUNT(CASE WHEN phone IS NOT NULL AND phone != '' THEN 1 END) as with_phone
FROM businesses;
```

### 4. Check Crawl Progress
```sql
SELECT 
  target_type,
  status,
  COUNT(*) as job_count,
  SUM(pages_scraped) as total_pages,
  SUM(rows_written) as total_rows
FROM scrape_jobs
GROUP BY target_type, status;
```

### 5. Get Recent Businesses
```sql
SELECT 
  business_name_ar,
  phone,
  email,
  city_slug,
  scraped_at
FROM businesses
ORDER BY scraped_at DESC
LIMIT 10;
```

### 6. Find Businesses by Keyword
```sql
SELECT DISTINCT
  b.business_name_ar,
  b.phone,
  b.email,
  b.city_slug
FROM businesses b
JOIN business_facets bf ON b.source_url = bf.source_url
WHERE bf.facet_type = 'keyword'
  AND bf.slug IN ('مصنع', 'factory', 'استيراد', 'import')
LIMIT 100;
```

### 7. Get Category Statistics
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

### 8. Check Running Jobs
```sql
SELECT 
  target_type,
  target_slug,
  city_slug,
  pages_scraped,
  rows_written,
  started_at
FROM scrape_jobs
WHERE status = 'running'
ORDER BY started_at DESC;
```

### 9. Get Failed Jobs
```sql
SELECT 
  target_type,
  target_slug,
  city_slug,
  error,
  started_at,
  finished_at
FROM scrape_jobs
WHERE status = 'failed'
ORDER BY finished_at DESC
LIMIT 20;
```

### 10. Database Size Check
```sql
SELECT 
  pg_size_pretty(pg_database_size('postgres')) as database_size,
  pg_size_pretty(pg_total_relation_size('businesses')) as businesses_table_size,
  pg_size_pretty(pg_total_relation_size('business_facets')) as facets_table_size;
```

## Useful Queries for Analysis

### Businesses by City
```sql
SELECT 
  city_slug,
  COUNT(*) as business_count
FROM businesses
WHERE city_slug IS NOT NULL
GROUP BY city_slug
ORDER BY business_count DESC;
```

### Email Coverage by City
```sql
SELECT 
  city_slug,
  COUNT(*) as total,
  COUNT(CASE WHEN email IS NOT NULL AND email != '' THEN 1 END) as with_email,
  ROUND(100.0 * COUNT(CASE WHEN email IS NOT NULL AND email != '' THEN 1 END) / COUNT(*), 2) as email_percentage
FROM businesses
WHERE city_slug IS NOT NULL
GROUP BY city_slug
ORDER BY email_percentage DESC;
```

### Most Common Categories
```sql
SELECT 
  category_slug,
  category_ar,
  COUNT(*) as count
FROM businesses
WHERE category_slug IS NOT NULL
GROUP BY category_slug, category_ar
ORDER BY count DESC
LIMIT 20;
```

### Crawl Performance by Target Type
```sql
SELECT 
  target_type,
  AVG(pages_scraped) as avg_pages,
  AVG(rows_written) as avg_rows,
  AVG(EXTRACT(EPOCH FROM (finished_at - started_at))/60) as avg_duration_minutes
FROM scrape_jobs
WHERE status = 'done'
  AND started_at IS NOT NULL
  AND finished_at IS NOT NULL
GROUP BY target_type;
```

### Recent Activity Timeline
```sql
SELECT 
  DATE(scraped_at::timestamptz) as date,
  COUNT(*) as businesses_added
FROM businesses
WHERE scraped_at IS NOT NULL
GROUP BY DATE(scraped_at::timestamptz)
ORDER BY date DESC
LIMIT 30;
```

## Data Maintenance Queries

### Reset Failed Jobs
```sql
UPDATE scrape_jobs
SET status = 'pending',
    error = '',
    started_at = NULL,
    finished_at = NULL
WHERE status = 'failed';
```

### Clean Old Completed Jobs
```sql
DELETE FROM scrape_jobs
WHERE status = 'done'
  AND finished_at < NOW() - INTERVAL '30 days';
```

### Find Businesses Without Facets
```sql
SELECT 
  b.source_url,
  b.business_name_ar,
  b.city_slug
FROM businesses b
LEFT JOIN business_facets bf ON b.source_url = bf.source_url
WHERE bf.source_url IS NULL;
```

### Update Business Category from Facets
```sql
UPDATE businesses b
SET category_slug = bf.slug,
    category_ar = bf.name_ar
FROM business_facets bf
WHERE b.source_url = bf.source_url
  AND bf.facet_type = 'category'
  AND (b.category_slug IS NULL OR b.category_slug = '');
```

## Performance Optimization

### Create Indexes (if needed)
```sql
-- Index on business_name_ar for faster searches
CREATE INDEX IF NOT EXISTS idx_businesses_name_ar ON businesses(business_name_ar);

-- Index on scraped_at for date filtering
CREATE INDEX IF NOT EXISTS idx_businesses_scraped_at ON businesses(scraped_at);

-- Index on facet lookups
CREATE INDEX IF NOT EXISTS idx_business_facets_slug ON business_facets(slug);
CREATE INDEX IF NOT EXISTS idx_business_facets_type_slug ON business_facets(facet_type, slug);
```

### Analyze Query Performance
```sql
EXPLAIN ANALYZE
SELECT 
  b.business_name_ar,
  b.phone,
  b.email
FROM businesses b
JOIN business_facets bf ON b.source_url = bf.source_url
WHERE bf.facet_type = 'keyword'
  AND bf.slug = 'مصنع'
LIMIT 100;
```

## Export Data

### Export Businesses to JSON
```sql
SELECT json_agg(row_to_json(t))
FROM (
  SELECT 
    business_name_ar,
    phone,
    email,
    address_ar,
    city_slug,
    category_ar
  FROM businesses
  WHERE email IS NOT NULL AND email != ''
) t;
```

### Export with Facets
```sql
SELECT 
  b.business_name_ar,
  b.phone,
  b.email,
  b.city_slug,
  array_agg(DISTINCT bf.slug) FILTER (WHERE bf.facet_type = 'keyword') as keywords,
  array_agg(DISTINCT bf.slug) FILTER (WHERE bf.facet_type = 'category') as categories
FROM businesses b
LEFT JOIN business_facets bf ON b.source_url = bf.source_url
GROUP BY b.source_url, b.business_name_ar, b.phone, b.email, b.city_slug
LIMIT 100;
```

## Monitoring Queries

### Check Database Health
```sql
SELECT 
  'businesses' as table_name,
  COUNT(*) as row_count,
  pg_size_pretty(pg_total_relation_size('businesses')) as size
UNION ALL
SELECT 
  'business_facets',
  COUNT(*),
  pg_size_pretty(pg_total_relation_size('business_facets'))
FROM business_facets
UNION ALL
SELECT 
  'scrape_jobs',
  COUNT(*),
  pg_size_pretty(pg_total_relation_size('scrape_jobs'))
FROM scrape_jobs;
```

### Active Connections
```sql
SELECT 
  COUNT(*) as active_connections,
  state,
  application_name
FROM pg_stat_activity
WHERE datname = 'postgres'
GROUP BY state, application_name;
```

### Long Running Queries
```sql
SELECT 
  pid,
  now() - query_start as duration,
  state,
  query
FROM pg_stat_activity
WHERE state != 'idle'
  AND query NOT LIKE '%pg_stat_activity%'
ORDER BY duration DESC;
```

## Tips

1. **Always use the project_id**: `brmljayacipdhfgppuzk`
2. **Test queries with LIMIT first**: Prevent large result sets
3. **Use EXPLAIN ANALYZE**: Check query performance before running on large datasets
4. **Batch operations**: Use transactions for multiple updates
5. **Monitor connection count**: Pooler has limits
6. **Regular backups**: Export data periodically
7. **Check RLS policies**: Ensure proper access control
8. **Use indexes wisely**: Balance query speed vs write performance

## Quick Actions

### Get Current Status
```sql
SELECT 
  (SELECT COUNT(*) FROM businesses) as total_businesses,
  (SELECT COUNT(*) FROM scrape_jobs WHERE status = 'running') as running_jobs,
  (SELECT COUNT(*) FROM scrape_jobs WHERE status = 'pending') as pending_jobs,
  (SELECT MAX(scraped_at) FROM businesses) as last_update;
```

### Data Quality Report
```sql
SELECT 
  'Total Businesses' as metric,
  COUNT(*)::text as value
FROM businesses
UNION ALL
SELECT 
  'With Arabic Names',
  COUNT(*)::text
FROM businesses
WHERE business_name_ar IS NOT NULL AND business_name_ar != ''
UNION ALL
SELECT 
  'With Emails',
  COUNT(*)::text
FROM businesses
WHERE email IS NOT NULL AND email != ''
UNION ALL
SELECT 
  'With Phones',
  COUNT(*)::text
FROM businesses
WHERE phone IS NOT NULL AND phone != '';
```

## Access Supabase Dashboard

**URL**: https://supabase.com/dashboard/project/brmljayacipdhfgppuzk

From the dashboard you can:
- View table data
- Run SQL queries
- Monitor performance
- Check logs
- Manage API keys
- Configure RLS policies
- View database size and usage
