# Database Status and Streamlit UI Updates

## Current Status ✅

### Database Configuration
- **Database Type**: Supabase PostgreSQL (Cloud)
- **Connection**: Successfully connected
- **Current Data**: 12,737 businesses (3,089 with Arabic names)
- **Configuration Files**:
  - `.env` - Contains DATABASE_URL for local development
  - `.streamlit/secrets.toml` - Contains DATABASE_URL for Streamlit local testing

### Streamlit UI Features
The Streamlit app (`app/streamlit_app.py`) already includes:

1. **Database Status Indicator**
   - Shows "🌐 Connected to Supabase (Cloud Database)" when using PostgreSQL
   - Shows "💾 Using Local SQLite Database" when using local database

2. **Data Export Features**
   - **Download Filtered CSV**: Exports businesses matching current filters
   - **Export All Data (Unfiltered)**: Downloads ALL businesses from database (up to 10M rows)

3. **Real-time Crawl Monitoring**
   - Live progress updates every 15 seconds
   - Shows running jobs, completed jobs, and newly added businesses
   - Displays crawl statistics and status

4. **Advanced Filtering**
   - Brands, Keywords, Cities, Areas, Districts
   - Arabic keyword expansion (e.g., 'مصنع' includes 'factory')
   - Search functionality across all business fields

## What's Already Working

### 1. Database Persistence
- All crawled data is stored in Supabase PostgreSQL
- Data persists across sessions and deployments
- No data loss when restarting the app

### 2. Data Synchronization
- New crawls automatically add data to the existing database
- Duplicate detection by `source_url` prevents redundant entries
- Existing businesses are skipped during crawls

### 3. Streamlit Cloud Deployment
- App can be deployed to Streamlit Cloud
- DATABASE_URL should be added to Streamlit Cloud secrets
- Starter taxonomy is automatically seeded on first launch

## Recommended Updates (Optional Enhancements)

### 1. Database Statistics Dashboard
Add a new section to show database health metrics:

```python
with st.expander("Database Statistics", expanded=False):
    stats = load_database_stats(DB_PATH)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Businesses", f"{stats['total_businesses']:,}")
    with col2:
        st.metric("With Arabic Names", f"{stats['arabic_businesses']:,}")
    with col3:
        st.metric("With Emails", f"{stats['businesses_with_email']:,}")
    with col4:
        st.metric("With Phones", f"{stats['businesses_with_phone']:,}")
```

### 2. Data Quality Indicators
Show data completeness for filtered results:

```python
if businesses:
    quality_metrics = calculate_quality_metrics(businesses)
    st.caption(
        f"📊 Data Quality: "
        f"{quality_metrics['email_rate']:.1%} have emails | "
        f"{quality_metrics['phone_rate']:.1%} have phones | "
        f"{quality_metrics['arabic_rate']:.1%} have Arabic names"
    )
```

### 3. Last Updated Timestamp
Show when the database was last updated:

```python
last_update = get_last_crawl_time(DB_PATH)
if last_update:
    st.sidebar.caption(f"Last updated: {last_update}")
```

### 4. Export Progress Indicator
For large exports, show progress:

```python
if st.button("Export All Data"):
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    with st.spinner("Loading all data..."):
        all_businesses = load_businesses_with_progress(
            DB_PATH, 
            progress_callback=lambda p: progress_bar.progress(p)
        )
    # ... rest of export logic
```

## Deployment Checklist

### For Streamlit Cloud Deployment:

1. **Add Secret to Streamlit Cloud**
   - Go to app settings → Secrets
   - Add:
     ```toml
     DATABASE_URL = "postgresql://postgres.brmljayacipdhfgppuzk:scrapping-database%40123@aws-1-eu-central-1.pooler.supabase.com:5432/postgres"
     ```

2. **Verify .gitignore**
   - Ensure `.streamlit/secrets.toml` is in `.gitignore`
   - Ensure `.env` is in `.gitignore`

3. **Test Locally First**
   ```bash
   streamlit run streamlit_app.py
   ```

4. **Deploy to Streamlit Cloud**
   - Push code to GitHub
   - Connect repository in Streamlit Cloud
   - Add DATABASE_URL secret
   - Deploy

## Database Maintenance

### Backup Strategy
```bash
# Export current data
python -c "from app.data_access import load_businesses; import pandas as pd; pd.DataFrame(load_businesses('$DATABASE_URL', {}, '', 10000000)).to_csv('backup.csv', index=False)"
```

### Monitor Database Size
```sql
SELECT 
    COUNT(*) as total_businesses,
    COUNT(DISTINCT category_slug) as unique_categories,
    COUNT(DISTINCT city_slug) as unique_cities,
    pg_size_pretty(pg_total_relation_size('businesses')) as table_size
FROM businesses;
```

### Clean Duplicate Data (if needed)
```sql
-- Find duplicates by source_url
SELECT source_url, COUNT(*) 
FROM businesses 
GROUP BY source_url 
HAVING COUNT(*) > 1;
```

## Current Database Schema

### Main Tables:
- **businesses**: Core business data (12,737 records)
- **business_facets**: Taxonomy associations (categories, keywords, locations)
- **categories**: Business categories
- **brands**: Brand taxonomy
- **keywords**: Keyword taxonomy
- **locations**: Cities, areas, districts
- **scrape_jobs**: Crawl job tracking

## Performance Optimization

### Current Optimizations:
1. **Batch Facet Loading**: Loads all facets in one query to avoid N+1 queries
2. **Indexed Queries**: Uses indexes on `source_url`, `slug`, `facet_type`
3. **Connection Pooling**: Uses Supabase pooler for efficient connections
4. **Limit Controls**: Default 1M row limit for UI queries

### Future Optimizations:
1. Add pagination for very large result sets
2. Implement result caching for common filter combinations
3. Add database indexes on frequently filtered columns
4. Consider materialized views for complex aggregations

## Troubleshooting

### Issue: "No businesses found"
- Check if DATABASE_URL is set correctly
- Verify database connection in verify_setup.py
- Check if taxonomy is seeded (should auto-seed on first run)

### Issue: "Slow query performance"
- Check database indexes
- Reduce result limit
- Use more specific filters
- Consider upgrading Supabase plan for better performance

### Issue: "Connection timeout"
- Verify network connectivity to Supabase
- Check if using correct pooler URL (not direct connection)
- Increase timeout settings in config

## Next Steps

1. ✅ Database is connected and working
2. ✅ Streamlit UI shows database status
3. ✅ Export functionality is available
4. 🔄 Optional: Implement recommended enhancements above
5. 🔄 Deploy to Streamlit Cloud with DATABASE_URL secret
6. 🔄 Monitor database growth and performance

## Support

For issues or questions:
1. Check `verify_setup.py` output for configuration status
2. Review Streamlit app logs in `output/streamlit.log`
3. Check Supabase dashboard for database metrics
4. Review crawl logs in `data/crawl.log`
