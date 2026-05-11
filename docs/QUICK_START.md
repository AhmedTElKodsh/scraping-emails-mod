# Quick Start Guide

Get up and running with the scraper in 5 minutes!

## 🚀 Choose Your Branch

### Option 1: Core Features Only (`main` branch)
```bash
git clone https://github.com/AhmedTElKodsh/scraping-emails-mod.git
cd scraping-emails-mod
git checkout main
```

### Option 2: Full Features with Apollo (`apollo-integration` branch)
```bash
git clone https://github.com/AhmedTElKodsh/scraping-emails-mod.git
cd scraping-emails-mod
git checkout apollo-integration
```

## 📦 Installation

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install browser for automation
playwright install chromium
```

## ⚡ Quick Commands

### 1. Scrape YellowPages (Both Branches)

```bash
# Scrape restaurants in Cairo
python -m scraper scrape restaurants --city cairo --limit 20

# Scrape all categories
python -m scraper crawl-all --max-pages 10
```

### 2. Launch Web UI (Both Branches)

```bash
# Main UI
python -m scraper ui

# Acquisition UI
python -m scraper acquisition-ui
```

### 3. Import CSV (Both Branches)

```bash
python -m scraper acquisition-import-csv your_leads.csv
```

### 4. Apollo Search (apollo-integration branch only)

```bash
# Set API key first
export APOLLO_API_KEY=your_key_here

# Run search
python -m scraper acquisition-apollo-search \
  --person-title "Owner" \
  --person-location "Egypt" \
  --live
```

## 📊 Output

Results are saved to:
- **CSV files**: `output/` directory
- **Database**: `data/scraper.sqlite`
- **Acquisition data**: `data/acquisition.sqlite`

## 🔧 Configuration

Create a `.env` file:

```env
# Rate limiting
RATE_LIMIT_MIN_DELAY=2.0
RATE_LIMIT_MAX_DELAY=8.0

# Database (optional - uses SQLite by default)
DATABASE_URL=postgresql://user:pass@host/db

# Apollo API (apollo-integration branch only)
APOLLO_API_KEY=your_api_key_here
```

## 📚 Next Steps

- Read [README.md](../README.md) for detailed documentation
- Check [BRANCHES.md](../BRANCHES.md) for branch strategy
- See [BRANCH_COMPARISON.md](BRANCH_COMPARISON.md) for feature comparison
- Review [CONTRIBUTING.md](../CONTRIBUTING.md) to contribute

## 🆘 Troubleshooting

### "Module not found" error
```bash
pip install -r requirements.txt
```

### "Playwright browser not found"
```bash
playwright install chromium
```

### "Apollo command not found"
```bash
# Make sure you're on apollo-integration branch
git checkout apollo-integration
```

### Database locked error
```bash
# Close any open Streamlit sessions
# Delete lock file if needed
rm data/scraper.sqlite-wal
```

## 💡 Tips

1. **Start with small limits** (`--limit 10`) to test
2. **Use `--dry-run`** for Apollo searches to test without API calls
3. **Check the UI** for easier data exploration
4. **Use `--headless false`** to see browser automation in action

## 🎯 Common Workflows

### Workflow 1: Quick YellowPages Scrape
```bash
python -m scraper scrape restaurants --city cairo --limit 50
# Results in: output/yellowpages_eg_category_restaurants_cairo_*.csv
```

### Workflow 2: Mass Crawl All Categories
```bash
# Initialize taxonomy first
python -m scraper taxonomy

# Run mass crawl
python -m scraper crawl-all --max-pages 20

# View results in UI
python -m scraper ui
```

### Workflow 3: Import and Manage Leads
```bash
# Import CSV
python -m scraper acquisition-import-csv leads.csv

# Launch acquisition UI to review
python -m scraper acquisition-ui
```

### Workflow 4: Apollo People Search (apollo-integration only)
```bash
# Set API key
export APOLLO_API_KEY=your_key

# Search for business owners in Egypt
python -m scraper acquisition-apollo-search \
  --person-title "Owner" \
  --person-title "CEO" \
  --person-location "Egypt" \
  --per-page 25 \
  --live

# View results in acquisition UI
python -m scraper acquisition-ui
```

## ✅ Verification

Test your installation:

```bash
# Run unit tests
pytest tests/unit -v

# Check code style
ruff check src/

# Verify CLI works
python -m scraper --help
```

You're all set! 🎉
