# Scraping Emails - Business Contact Scraper

![Branch](https://img.shields.io/badge/branch-apollo--integration-green)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Educational-green)
![Apollo](https://img.shields.io/badge/Apollo-Included-brightgreen)

A Python-based web scraping tool for collecting business contact information from YellowPages Egypt and other compliant acquisition sources.

## 🌿 Branch Structure

This repository uses **separate branches** for different feature sets:

### 🚀 `apollo-integration` Branch (Current)
This branch contains the **full feature set** including Apollo.io API integration:
- ✅ YellowPages Egypt scraper
- ✅ CSV import/export functionality
- ✅ Acquisition database and UI
- ✅ Core pipeline and browser automation
- ✅ Streamlit web interface
- ✅ **Apollo People Search API integration**
- ✅ **Apollo public site scraper**
- ✅ **Apollo CLI commands**

### 📌 `main` Branch
The main branch contains only the **core scraping functionality** without Apollo integration.

**To use core features only (without Apollo):**
```bash
git checkout main
```

See [BRANCHES.md](BRANCHES.md) for detailed branch documentation.

## 🚀 Features

- **Multi-tier scraping pipeline** with automatic fallback
- **YellowPages Egypt** category, brand, and keyword search
- **Browser automation** with Playwright for JavaScript-heavy sites
- **Rate limiting** and proxy support
- **SQLite/PostgreSQL** storage with Supabase integration
- **Streamlit UI** for data exploration and management
- **Compliant acquisition** workflow with separate database
- **CSV import/export** for user-owned data

## 📋 Requirements

- Python 3.10+
- Playwright (for browser automation)
- SQLite or PostgreSQL database

## 🔧 Installation

1. Clone the repository:
```bash
git clone https://github.com/AhmedTElKodsh/scraping-emails-mod.git
cd scraping-emails-mod
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install chromium
```

4. Set up environment variables (optional):
```bash
cp .env.example .env
# Edit .env with your configuration
```

## 🎯 Usage

### Command Line Interface

**Scrape YellowPages by category:**
```bash
python -m scraper scrape restaurants --limit 50
```

**Scrape with city filter:**
```bash
python -m scraper scrape restaurants --city cairo
```

**Mass crawl all categories:**
```bash
python -m scraper crawl-all --max-pages 20
```

**Initialize taxonomy (categories + locations):**
```bash
python -m scraper taxonomy
```

### Web Interface

**Launch the main Streamlit UI:**
```bash
python -m scraper ui
```

**Launch the acquisition workbench:**
```bash
python -m scraper acquisition-ui
```

### Acquisition Workflow

**Import user-owned CSV:**
```bash
python -m scraper acquisition-import-csv leads.csv --source-note "Trade show contacts"
```

**Apollo People Search (apollo-integration branch only):**
```bash
# Set your Apollo API key
export APOLLO_API_KEY=your_api_key_here

# Run Apollo people search
python -m scraper acquisition-apollo-search \
  --person-title "Owner" \
  --person-title "CEO" \
  --person-location "Egypt" \
  --person-location "United Arab Emirates" \
  --live

# Dry run (no API call)
python -m scraper acquisition-apollo-search \
  --person-title "Owner" \
  --person-location "Egypt" \
  --dry-run
```

## 📁 Project Structure

```
scraping-emails-mod/
├── src/scraper/          # Core scraping logic
│   ├── sites/            # Site-specific scrapers
│   ├── cli.py            # Command-line interface
│   ├── pipeline.py       # Multi-tier scraping pipeline
│   ├── browser_client.py # Playwright browser automation
│   └── acquisition_*.py  # Acquisition database logic
├── app/                  # Streamlit applications
├── tests/                # Unit and integration tests
├── data/                 # SQLite databases and seed data
├── output/               # CSV export files
└── docs/                 # Documentation

```

## 🧪 Testing

Run the test suite:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=scraper --cov-report=html
```

## 🔒 Compliance & Ethics

This tool is designed for **compliant data acquisition**:
- Respects robots.txt and rate limits
- Separate acquisition database for tracking data provenance
- Policy-based source management
- User-owned data import workflow
- No unauthorized API scraping

## 🛠️ Configuration

Configuration is managed through environment variables or `.env` file:

```env
# Rate limiting
RATE_LIMIT_MIN_DELAY=2.0
RATE_LIMIT_MAX_DELAY=8.0

# Database
DATABASE_URL=postgresql://user:pass@host/db
DB_PATH=data/scraper.sqlite
ACQUISITION_DB_PATH=data/acquisition.sqlite

# Browser
BROWSER_HEADLESS=true
BROWSER_TIMEOUT_MS=30000

# Mass crawl
MASS_CRAWL_MAX_PAGES=20

# Apollo API (apollo-integration branch only)
APOLLO_API_KEY=your_apollo_api_key_here
APOLLO_API_BASE_URL=https://api.apollo.io/api/v1
APOLLO_DEFAULT_PERSON_LOCATIONS=United States, United Kingdom, Canada, Australia, Germany, France, United Arab Emirates, Saudi Arabia, Egypt
```

## 📊 Database Schema

The project uses two separate databases:

1. **Main Database** (`scraper.sqlite`): YellowPages scraping results
2. **Acquisition Database** (`acquisition.sqlite`): Compliant acquisition sources with provenance tracking

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is for educational and research purposes. Ensure compliance with applicable laws and terms of service when scraping websites.

## 🔗 Links

- **Repository**: https://github.com/AhmedTElKodsh/scraping-emails-mod
- **Main Branch**: https://github.com/AhmedTElKodsh/scraping-emails-mod/tree/main
- **Apollo Integration Branch**: https://github.com/AhmedTElKodsh/scraping-emails-mod/tree/apollo-integration

## 📧 Support

For issues and questions, please open an issue on GitHub.

---

**Note**: You are currently on the `apollo-integration` branch which includes Apollo.io API features. To use the core features without Apollo, switch to the `main` branch. See [BRANCHES.md](BRANCHES.md) for details.
