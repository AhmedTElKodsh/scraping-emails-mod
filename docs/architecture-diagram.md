# System Architecture Diagram

## Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                               │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Streamlit Web Application                       │   │
│  │                 (app/streamlit_app.py)                       │   │
│  │                                                               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │   │
│  │  │   Filters    │  │  Statistics  │  │    Export    │      │   │
│  │  │   Sidebar    │  │  Dashboard   │  │   Controls   │      │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │   │
│  │                                                               │   │
│  │  ┌──────────────────────────────────────────────────────┐   │   │
│  │  │         Business Data Table (Real-time)              │   │   │
│  │  │  • Arabic names  • Phones  • Emails  • Addresses    │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  │                                                               │   │
│  │  ┌──────────────────────────────────────────────────────┐   │   │
│  │  │         Crawl Progress Monitor (Auto-refresh)        │   │   │
│  │  │  • Running jobs  • Progress bars  • Statistics      │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP/WebSocket
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA ACCESS LAYER                               │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Data Access Module                              │   │
│  │              (app/data_access.py)                            │   │
│  │                                                               │   │
│  │  • load_businesses()         • load_database_stats()        │   │
│  │  • load_crawl_progress()     • get_last_crawl_time()        │   │
│  │  • load_facet_options()      • load_job_summary()           │   │
│  │  • search_facet_suggestions()                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ SQL Queries
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      STORAGE LAYER                                   │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │           Storage Abstraction (scraper/storage.py)           │   │
│  │                                                               │   │
│  │  • open_connection()    • Backend detection (SQLite/Postgres)│   │
│  │  • is_postgres_url()    • Connection pooling                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
│         ┌─────────────────────┐      ┌─────────────────────┐       │
│         │   SQLite Backend    │      │  PostgreSQL Backend │       │
│         │   (Local Dev)       │      │   (Production)      │       │
│         └─────────────────────┘      └─────────────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Connection String
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DATABASE (Supabase PostgreSQL)                    │
│                                                                       │
│  Project: scrapping-database (brmljayacipdhfgppuzk)                 │
│  Region: eu-central-1 (Frankfurt)                                    │
│  Version: PostgreSQL 17.6.1.121                                      │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                        TABLES                                 │  │
│  │                                                                │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │  │
│  │  │   businesses    │  │ business_facets │  │  categories  │ │  │
│  │  │   (13,232)      │  │   (60,540)      │  │    (720)     │ │  │
│  │  └─────────────────┘  └─────────────────┘  └──────────────┘ │  │
│  │                                                                │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │  │
│  │  │     brands      │  │    keywords     │  │  locations   │ │  │
│  │  │    (4,994)      │  │     (113)       │  │    (384)     │ │  │
│  │  └─────────────────┘  └─────────────────┘  └──────────────┘ │  │
│  │                                                                │  │
│  │  ┌─────────────────┐  ┌─────────────────┐                    │  │
│  │  │  scrape_jobs    │  │  schema_meta    │                    │  │
│  │  │   (70,088)      │  │      (1)        │                    │  │
│  │  └─────────────────┘  └─────────────────┘                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  Features:                                                            │
│  • Row Level Security (RLS) enabled on all tables                   │
│  • Foreign key constraints for data integrity                        │
│  • Indexes on primary keys and frequently queried columns           │
│  • Connection pooling via Supavisor                                  │
└─────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
                                    │ Crawl Data
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                      CRAWLER SYSTEM                                  │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │           Mass Crawl Orchestrator                            │   │
│  │           (scraper/mass_crawl.py)                            │   │
│  │                                                                │   │
│  │  • Job queue management                                       │   │
│  │  • Parallel crawling                                          │   │
│  │  • Progress tracking                                          │   │
│  │  • Error handling & retry logic                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                    │                                  │
│                                    ▼                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Scraper Engine                                  │   │
│  │              (scraper/scraper.py)                            │   │
│  │                                                                │   │
│  │  • Playwright browser automation                             │   │
│  │  • Rate limiting & proxy support                             │   │
│  │  • HTML parsing & data extraction                            │   │
│  │  • Arabic text handling                                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                    │                                  │
│                                    ▼                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Data Writers                                    │   │
│  │                                                                │   │
│  │  ┌──────────────────┐      ┌──────────────────┐            │   │
│  │  │  SQLite Writer   │      │ PostgreSQL Writer│            │   │
│  │  │  (Local Dev)     │      │  (Production)    │            │   │
│  │  └──────────────────┘      └──────────────────┘            │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
                                    │ HTTP Requests
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL DATA SOURCE                              │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Yellow Pages Egypt                              │   │
│  │              (yellowpages.com.eg)                            │   │
│  │                                                                │   │
│  │  • Business listings                                          │   │
│  │  • Category taxonomy                                          │   │
│  │  • Location data                                              │   │
│  │  • Contact information                                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Crawling Flow
```
Yellow Pages → Scraper Engine → Data Writer → Supabase → Streamlit UI
```

### 2. User Query Flow
```
User Filter → Streamlit UI → Data Access → Supabase → Results Display
```

### 3. Export Flow
```
User Request → Data Access → Supabase → CSV Generation → Download
```

## Component Details

### Frontend (Streamlit)
- **Technology**: Python Streamlit
- **Features**: 
  - Real-time data display
  - Interactive filtering
  - Auto-refresh during crawls
  - CSV export
  - Statistics dashboard
- **Deployment**: Streamlit Cloud or local

### Data Access Layer
- **Technology**: Python with psycopg (PostgreSQL) / sqlite3
- **Features**:
  - Database abstraction
  - Query optimization
  - Connection pooling
  - Error handling
- **Functions**: 15+ data access functions

### Storage Layer
- **Primary**: Supabase PostgreSQL (Cloud)
- **Fallback**: SQLite (Local development)
- **Features**:
  - Automatic backend detection
  - Connection pooling
  - Transaction support
  - RLS security

### Crawler System
- **Technology**: Python + Playwright
- **Features**:
  - Parallel job execution
  - Rate limiting
  - Proxy support
  - Error recovery
  - Progress tracking
- **Capacity**: 70,000+ jobs queued

### Database (Supabase)
- **Type**: PostgreSQL 17.6
- **Location**: AWS eu-central-1
- **Size**: ~60MB
- **Records**: 13,232 businesses
- **Features**:
  - RLS enabled
  - Foreign keys
  - Indexes
  - Connection pooling

## Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Layers                           │
│                                                               │
│  1. Network Layer                                            │
│     • HTTPS/TLS encryption                                   │
│     • Supabase connection pooling                            │
│     • IP whitelisting (optional)                             │
│                                                               │
│  2. Authentication Layer                                     │
│     • Database credentials in environment variables          │
│     • Streamlit secrets management                           │
│     • No credentials in code                                 │
│                                                               │
│  3. Database Layer                                           │
│     • Row Level Security (RLS) on all tables                │
│     • Foreign key constraints                                │
│     • Input validation                                       │
│     • SQL injection prevention                               │
│                                                               │
│  4. Application Layer                                        │
│     • Error handling                                         │
│     • Rate limiting                                          │
│     • Data validation                                        │
│     • Sanitized outputs                                      │
└─────────────────────────────────────────────────────────────┘
```

## Deployment Architecture

### Local Development
```
Developer Machine
├── SQLite Database (data/scraper.sqlite)
├── Streamlit App (localhost:8501)
├── Crawler (manual execution)
└── .env file (local config)
```

### Production (Streamlit Cloud)
```
Streamlit Cloud
├── Streamlit App (public URL)
├── Secrets (DATABASE_URL)
└── Auto-deploy from GitHub
         │
         ▼
    Supabase Cloud
    ├── PostgreSQL Database
    ├── Connection Pooler
    └── Monitoring Dashboard
```

## Monitoring & Observability

```
┌─────────────────────────────────────────────────────────────┐
│                    Monitoring Stack                          │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Supabase Dashboard                                  │   │
│  │  • Database metrics                                  │   │
│  │  • Query performance                                 │   │
│  │  • Connection count                                  │   │
│  │  • Storage usage                                     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Streamlit UI                                        │   │
│  │  • Database statistics                               │   │
│  │  • Crawl progress                                    │   │
│  │  • Data quality metrics                              │   │
│  │  • Last update timestamp                             │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Application Logs                                    │   │
│  │  • output/streamlit.log                              │   │
│  │  • data/crawl.log                                    │   │
│  │  • Error tracking                                    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Scalability Considerations

### Current Capacity
- **Database**: 13K businesses, room for millions
- **Crawl Jobs**: 70K jobs queued
- **Concurrent Users**: Limited by Streamlit Cloud tier
- **Export Size**: Up to 10M rows supported

### Scaling Options
1. **Vertical Scaling**: Upgrade Supabase plan
2. **Horizontal Scaling**: Add read replicas
3. **Caching**: Implement Redis for frequent queries
4. **CDN**: Cache static assets
5. **Load Balancing**: Multiple Streamlit instances

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Streamlit | Web UI |
| Backend | Python | Business logic |
| Database | PostgreSQL (Supabase) | Data storage |
| Crawler | Playwright | Web scraping |
| Deployment | Streamlit Cloud | Hosting |
| Monitoring | Supabase Dashboard | Observability |
| Version Control | Git/GitHub | Code management |

## Integration Points

### External Services
- **Supabase**: Database hosting
- **Streamlit Cloud**: App hosting
- **Yellow Pages Egypt**: Data source
- **GitHub**: Code repository

### Internal Modules
- **scraper/**: Crawling logic
- **app/**: UI and data access
- **data/**: Local storage
- **docs/**: Documentation
- **.streamlit/**: Configuration

## Future Architecture Enhancements

1. **Caching Layer**: Redis for frequent queries
2. **API Layer**: REST API for external access
3. **Queue System**: Celery for background jobs
4. **Analytics**: Data warehouse for insights
5. **Notifications**: Email/SMS alerts for crawl completion
6. **Authentication**: User login and permissions
7. **Multi-tenancy**: Support multiple organizations
