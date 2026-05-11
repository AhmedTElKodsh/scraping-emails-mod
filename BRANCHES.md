# Branch Structure

This repository uses separate branches to organize different features:

## Main Branch (`main`)
The main branch contains the core scraping functionality without Apollo integration:
- YellowPages Egypt scraper
- CSV import/export functionality
- Acquisition database and UI
- Core pipeline and browser automation
- **Does NOT include Apollo API integration**

## Apollo Integration Branch (`apollo-integration`)
The `apollo-integration` branch contains all Apollo-related code:
- Apollo People Search API integration (`src/scraper/apollo_people_search.py`)
- Apollo public site scraper (`src/scraper/sites/apollo_public.py`)
- Apollo CLI commands (`acquisition-apollo-search`)
- Apollo configuration settings
- Apollo-related tests

### Working with Apollo Features

To use Apollo features:

```bash
# Switch to the apollo-integration branch
git checkout apollo-integration

# Install dependencies (if needed)
pip install -r requirements.txt

# Use Apollo commands
python -m scraper acquisition-apollo-search --person-title "Owner" --person-location "Egypt"
```

### Merging Changes

When making changes that should be in both branches:
1. Make changes in `main` first
2. Merge `main` into `apollo-integration`:
   ```bash
   git checkout apollo-integration
   git merge main
   git push origin apollo-integration
   ```

### Why Separate Branches?

The Apollo integration is kept separate to:
- Maintain a clean core codebase without external API dependencies
- Allow users to choose whether they need Apollo features
- Simplify compliance and licensing considerations
- Make it easier to maintain and test the core functionality independently
