# Branch Strategy & Architecture

## 🌳 Branch Structure Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         REPOSITORY                           │
│         github.com/AhmedTElKodsh/scraping-emails-mod        │
└─────────────────────────────────────────────────────────────┘
                              │
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
        ┌───────────────┐          ┌──────────────────┐
        │  main branch  │          │ apollo-integration│
        │   (default)   │          │     branch        │
        └───────────────┘          └──────────────────┘
                │                           │
                │                           │
        ┌───────┴────────┐         ┌────────┴─────────┐
        │                │         │                  │
        ▼                ▼         ▼                  ▼
    Core Features    No Apollo   Core Features   Apollo Features
    ✅ YellowPages   ❌ Apollo   ✅ YellowPages  ✅ Apollo API
    ✅ CSV I/O                   ✅ CSV I/O      ✅ Apollo Scraper
    ✅ Acquisition               ✅ Acquisition  ✅ Apollo CLI
    ✅ Streamlit                 ✅ Streamlit
    ✅ Browser                   ✅ Browser
```

## 🔄 Development Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    DEVELOPMENT WORKFLOW                       │
└──────────────────────────────────────────────────────────────┘

1. Core Feature Development
   ┌─────────────┐
   │ Developer   │
   └──────┬──────┘
          │
          ▼
   ┌─────────────────┐
   │ Create feature  │
   │ branch from     │──────► feature/new-core-feature
   │ main            │
   └─────────────────┘
          │
          ▼
   ┌─────────────────┐
   │ Develop & Test  │
   └─────────────────┘
          │
          ▼
   ┌─────────────────┐
   │ PR to main      │
   └─────────────────┘
          │
          ▼
   ┌─────────────────┐
   │ Merge to main   │
   └─────────────────┘
          │
          ▼
   ┌─────────────────────────┐
   │ Sync to apollo-         │
   │ integration (manual     │
   │ or automated)           │
   └─────────────────────────┘


2. Apollo Feature Development
   ┌─────────────┐
   │ Developer   │
   └──────┬──────┘
          │
          ▼
   ┌─────────────────────┐
   │ Create feature      │
   │ branch from         │──────► feature/apollo-new-feature
   │ apollo-integration  │
   └─────────────────────┘
          │
          ▼
   ┌─────────────────────┐
   │ Develop & Test      │
   └─────────────────────┘
          │
          ▼
   ┌─────────────────────┐
   │ PR to apollo-       │
   │ integration         │
   └─────────────────────┘
          │
          ▼
   ┌─────────────────────┐
   │ Merge to apollo-    │
   │ integration         │
   └─────────────────────┘
```

## 📋 Branch Responsibilities

### `main` Branch

**Purpose**: Stable, core functionality without external API dependencies

**Contains**:
- YellowPages Egypt scraper
- CSV import/export
- Acquisition database framework
- Streamlit UI
- Browser automation
- Core pipeline
- Rate limiting
- Proxy support

**Does NOT Contain**:
- Apollo API integration
- Apollo-specific scrapers
- Apollo CLI commands
- Apollo configuration

**Protected**: Yes (recommended)
**Default Branch**: Yes
**CI/CD**: Runs on every push

### `apollo-integration` Branch

**Purpose**: Full feature set including Apollo.io integration

**Contains**:
- Everything from `main` branch
- Apollo People Search API
- Apollo public site scraper
- Apollo CLI commands
- Apollo configuration
- Apollo tests

**Protected**: Yes (recommended)
**Default Branch**: No
**CI/CD**: Runs on every push

## 🔀 Merge Strategy

### Syncing Changes from `main` to `apollo-integration`

```bash
# Method 1: Merge (recommended for multiple commits)
git checkout apollo-integration
git merge main
git push origin apollo-integration

# Method 2: Cherry-pick (for specific commits)
git checkout apollo-integration
git cherry-pick <commit-hash>
git push origin apollo-integration

# Method 3: Rebase (for clean history)
git checkout apollo-integration
git rebase main
git push origin apollo-integration --force-with-lease
```

### When to Sync

- ✅ After merging core features to `main`
- ✅ After bug fixes in `main`
- ✅ After documentation updates
- ✅ Weekly (if active development)
- ❌ Don't sync Apollo-specific changes back to `main`

## 🎯 Decision Tree: Which Branch?

```
                    ┌─────────────────────┐
                    │ What are you doing? │
                    └──────────┬──────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
    ┌───────────────────────┐    ┌──────────────────────┐
    │ Core feature/bug fix  │    │ Apollo-related work  │
    └───────────┬───────────┘    └──────────┬───────────┘
                │                            │
                ▼                            ▼
        ┌───────────────┐          ┌─────────────────────┐
        │  Use main     │          │ Use apollo-         │
        │  branch       │          │ integration branch  │
        └───────────────┘          └─────────────────────┘
                │                            │
                ▼                            ▼
    ┌───────────────────────┐    ┌──────────────────────┐
    │ 1. Fork from main     │    │ 1. Fork from apollo- │
    │ 2. Create feature     │    │    integration       │
    │    branch             │    │ 2. Create feature    │
    │ 3. Develop            │    │    branch            │
    │ 4. PR to main         │    │ 3. Develop           │
    │ 5. Sync to apollo-    │    │ 4. PR to apollo-     │
    │    integration        │    │    integration       │
    └───────────────────────┘    └──────────────────────┘
```

## 🛡️ Branch Protection Rules (Recommended)

### For `main` Branch

```yaml
Protection Rules:
  - Require pull request reviews: 1
  - Require status checks to pass: Yes
    - CI/CD tests
    - Linting
  - Require branches to be up to date: Yes
  - Include administrators: No
  - Restrict who can push: Yes (maintainers only)
  - Allow force pushes: No
  - Allow deletions: No
```

### For `apollo-integration` Branch

```yaml
Protection Rules:
  - Require pull request reviews: 1
  - Require status checks to pass: Yes
    - CI/CD tests (including Apollo tests)
    - Linting
  - Require branches to be up to date: Yes
  - Include administrators: No
  - Restrict who can push: Yes (maintainers only)
  - Allow force pushes: No
  - Allow deletions: No
```

## 📊 File Organization

### Shared Files (Both Branches)

```
src/scraper/
├── __init__.py
├── __main__.py
├── cli.py                    # Core commands
├── config.py                 # Core config
├── pipeline.py
├── browser_client.py
├── http_client.py
├── csv_writer.py
├── acquisition_db.py
├── acquisition_csv.py
└── sites/
    ├── __init__.py
    └── yellowpages_eg.py
```

### Apollo-Only Files (apollo-integration Branch)

```
src/scraper/
├── apollo_people_search.py   # Apollo API
└── sites/
    └── apollo_public.py      # Apollo scraper

tests/unit/
├── test_apollo_people_search.py
└── test_apollo_parser.py
```

## 🔍 Code Review Guidelines

### For `main` Branch PRs

**Check**:
- [ ] No Apollo imports
- [ ] No Apollo configuration
- [ ] Tests pass without Apollo
- [ ] Documentation updated
- [ ] No breaking changes

**Reject if**:
- Contains Apollo-specific code
- Breaks existing functionality
- Missing tests

### For `apollo-integration` Branch PRs

**Check**:
- [ ] Apollo changes isolated to Apollo files
- [ ] Core changes also in `main` (or will be)
- [ ] Apollo tests included
- [ ] API key handling secure
- [ ] Documentation updated

**Reject if**:
- Core changes not in `main` first
- Breaks Apollo functionality
- Missing Apollo tests

## 🚀 Release Strategy

### Versioning

```
v1.0.0-main          # Release from main branch
v1.0.0-apollo        # Release from apollo-integration branch
```

### Release Process

1. **Tag `main` branch**:
   ```bash
   git checkout main
   git tag -a v1.0.0-main -m "Release v1.0.0 (core features)"
   git push origin v1.0.0-main
   ```

2. **Tag `apollo-integration` branch**:
   ```bash
   git checkout apollo-integration
   git tag -a v1.0.0-apollo -m "Release v1.0.0 (with Apollo)"
   git push origin v1.0.0-apollo
   ```

## 📈 Metrics & Monitoring

### Branch Health Indicators

**main Branch**:
- ✅ All tests passing
- ✅ No Apollo dependencies
- ✅ Clean commit history
- ✅ Up-to-date documentation

**apollo-integration Branch**:
- ✅ All tests passing (including Apollo)
- ✅ Synced with main
- ✅ Apollo features working
- ✅ Up-to-date documentation

## 🎓 Best Practices

1. **Always develop core features in `main` first**
2. **Keep Apollo code isolated in apollo-integration**
3. **Sync regularly from main to apollo-integration**
4. **Never merge apollo-integration back to main**
5. **Use descriptive commit messages**
6. **Tag releases on both branches**
7. **Keep documentation in sync**
8. **Run tests before pushing**

## 📞 Support

Questions about branch strategy?
- Check [BRANCHES.md](../BRANCHES.md)
- See [CONTRIBUTING.md](../CONTRIBUTING.md)
- Open an issue with `question` label
