# Branch Comparison Guide

This document provides a detailed comparison between the `main` and `apollo-integration` branches.

## 📊 Quick Comparison Table

| Feature | `main` Branch | `apollo-integration` Branch |
|---------|---------------|----------------------------|
| YellowPages Scraper | ✅ Yes | ✅ Yes |
| CSV Import/Export | ✅ Yes | ✅ Yes |
| Acquisition Database | ✅ Yes | ✅ Yes |
| Streamlit UI | ✅ Yes | ✅ Yes |
| Browser Automation | ✅ Yes | ✅ Yes |
| Proxy Support | ✅ Yes | ✅ Yes |
| Apollo People Search API | ❌ No | ✅ Yes |
| Apollo Public Scraper | ❌ No | ✅ Yes |
| Apollo CLI Commands | ❌ No | ✅ Yes |
| Apollo Configuration | ❌ No | ✅ Yes |

## 📁 File Differences

### Files ONLY in `apollo-integration` Branch

```
src/scraper/
├── apollo_people_search.py          # Apollo API integration
└── sites/
    └── apollo_public.py              # Apollo public site scraper

tests/unit/
├── test_apollo_people_search.py     # Apollo API tests
└── test_apollo_parser.py            # Apollo parser tests
```

### Configuration Differences

#### `src/scraper/config.py`

**main branch:**
```python
# No Apollo settings
db_path: str = "data/scraper.sqlite"
acquisition_db_path: str = "data/acquisition.sqlite"
mass_crawl_max_pages: int = Field(20, ge=1)
```

**apollo-integration branch:**
```python
# Includes Apollo settings
db_path: str = "data/scraper.sqlite"
acquisition_db_path: str = "data/acquisition.sqlite"
apollo_api_key: str = ""
apollo_api_base_url: str = "https://api.apollo.io/api/v1"
apollo_default_person_locations: str = "United States, United Kingdom, ..."
mass_crawl_max_pages: int = Field(20, ge=1)
```

### CLI Command Differences

#### `src/scraper/cli.py`

**main branch commands:**
- `scrape` - YellowPages scraper
- `taxonomy` - Initialize taxonomy
- `crawl-all` - Mass crawl
- `ui` - Launch Streamlit UI
- `acquisition-ui` - Launch acquisition UI
- `acquisition-import-csv` - Import CSV

**apollo-integration branch commands:**
- All commands from main branch, PLUS:
- `acquisition-apollo-search` - Apollo People Search API

## 🔧 Usage Examples

### Main Branch Usage

```bash
# Switch to main branch
git checkout main

# Scrape YellowPages
python -m scraper scrape restaurants --city cairo

# Import user-owned CSV
python -m scraper acquisition-import-csv leads.csv

# Launch UI
python -m scraper ui
```

### Apollo Integration Branch Usage

```bash
# Switch to apollo-integration branch
git checkout apollo-integration

# All main branch commands work, PLUS:

# Set Apollo API key
export APOLLO_API_KEY=your_key_here

# Run Apollo People Search
python -m scraper acquisition-apollo-search \
  --person-title "Owner" \
  --person-location "Egypt" \
  --live

# Dry run (no API call)
python -m scraper acquisition-apollo-search \
  --person-title "CEO" \
  --person-location "United Arab Emirates" \
  --dry-run
```

## 🧪 Test Coverage Differences

### Main Branch Tests
- ✅ YellowPages scraper tests
- ✅ CSV import/export tests
- ✅ Pipeline tests
- ✅ Browser automation tests
- ✅ Acquisition database tests
- ✅ Configuration tests
- ✅ CLI tests (without Apollo)

### Apollo Integration Branch Tests
- ✅ All tests from main branch
- ✅ Apollo People Search API tests
- ✅ Apollo parser tests
- ✅ Apollo CLI command tests
- ✅ Apollo configuration tests

## 📦 Dependencies

Both branches share the same dependencies in `requirements.txt`:
- playwright
- beautifulsoup4
- requests
- typer
- streamlit
- supabase
- etc.

No additional dependencies are required for Apollo features (uses standard HTTP library).

## 🔄 Keeping Branches in Sync

### Workflow for Core Changes

1. Make changes in `main` branch first
2. Test and commit to `main`
3. Cherry-pick or merge to `apollo-integration`:

```bash
# Option 1: Cherry-pick specific commits
git checkout apollo-integration
git cherry-pick <commit-hash>

# Option 2: Merge main into apollo-integration
git checkout apollo-integration
git merge main
```

### Workflow for Apollo Changes

1. Make changes directly in `apollo-integration` branch
2. Only touch Apollo-specific files
3. Test and commit to `apollo-integration`

## 🎯 When to Use Which Branch

### Use `main` Branch When:
- ✅ You don't need Apollo API features
- ✅ You want a simpler, focused codebase
- ✅ You're contributing core features
- ✅ You're fixing bugs in core functionality
- ✅ You want to avoid external API dependencies

### Use `apollo-integration` Branch When:
- ✅ You need Apollo People Search API
- ✅ You want to scrape Apollo public pages
- ✅ You're working on Apollo-specific features
- ✅ You need the full feature set

## 🔍 Code Review Checklist

### For PRs to `main` Branch:
- [ ] No Apollo-specific code included
- [ ] No `apollo_people_search.py` imports
- [ ] No `apollo_public.py` imports
- [ ] No Apollo configuration settings
- [ ] Tests pass without Apollo dependencies

### For PRs to `apollo-integration` Branch:
- [ ] Apollo-specific changes only touch Apollo files
- [ ] Core changes are also in `main` (or will be merged)
- [ ] Apollo tests included
- [ ] Apollo API key handling is secure

## 📈 Branch Statistics

### Main Branch
- **Lines of Code**: ~8,500 (excluding tests)
- **Test Files**: 15+
- **CLI Commands**: 6
- **Site Scrapers**: 1 (YellowPages)

### Apollo Integration Branch
- **Lines of Code**: ~9,400 (excluding tests)
- **Test Files**: 17+
- **CLI Commands**: 7
- **Site Scrapers**: 2 (YellowPages + Apollo)

## 🚀 Migration Guide

### From Main to Apollo Integration

```bash
# Save your current work
git stash

# Switch to apollo-integration
git checkout apollo-integration

# Restore your work
git stash pop

# Set up Apollo API key
echo "APOLLO_API_KEY=your_key_here" >> .env
```

### From Apollo Integration to Main

```bash
# Save your current work (excluding Apollo files)
git stash

# Switch to main
git checkout main

# Restore your work
git stash pop

# Note: Apollo-specific code will not work on main branch
```

## 📝 Summary

- **`main` branch**: Clean, focused, core functionality only
- **`apollo-integration` branch**: Full feature set with Apollo API
- Both branches are actively maintained
- Core changes flow from `main` → `apollo-integration`
- Apollo changes stay in `apollo-integration`

Choose the branch that fits your needs!
