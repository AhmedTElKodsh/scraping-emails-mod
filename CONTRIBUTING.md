# Contributing to Scraping Emails

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## 🌿 Branch Strategy

This project uses a **dual-branch strategy**:

### `main` Branch
- Contains core scraping functionality
- **No Apollo API integration**
- All core features and bug fixes go here first
- This is the default branch for most contributions

### `apollo-integration` Branch
- Contains everything from `main` PLUS Apollo API features
- Apollo-specific code lives only here
- Periodically syncs non-Apollo changes from `main`

## 🔄 Contribution Workflow

### For Core Features (Non-Apollo)

1. **Fork and clone** the repository
2. **Create a feature branch** from `main`:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes** and commit:
   ```bash
   git add .
   git commit -m "Add: your feature description"
   ```

4. **Run tests** before pushing:
   ```bash
   pytest tests/unit
   ruff check src/ tests/
   ```

5. **Push and create a Pull Request** to `main`:
   ```bash
   git push origin feature/your-feature-name
   ```

### For Apollo-Specific Features

1. **Create a feature branch** from `apollo-integration`:
   ```bash
   git checkout apollo-integration
   git pull origin apollo-integration
   git checkout -b feature/apollo-your-feature-name
   ```

2. **Make your changes** (only Apollo-related code)

3. **Run tests** including Apollo tests:
   ```bash
   pytest tests/unit
   ```

4. **Push and create a Pull Request** to `apollo-integration`

### For Bug Fixes

- If the bug exists in **both branches**: Fix it in `main` first, then it will be synced to `apollo-integration`
- If the bug is **Apollo-specific**: Fix it directly in `apollo-integration`

## 📝 Commit Message Guidelines

Use clear, descriptive commit messages:

- `Add: new feature description`
- `Fix: bug description`
- `Update: what was updated`
- `Refactor: what was refactored`
- `Docs: documentation changes`
- `Test: test additions or changes`

## 🧪 Testing Requirements

All contributions must include tests:

1. **Unit tests** for new functions/classes
2. **Integration tests** for new workflows
3. All existing tests must pass

Run tests locally:
```bash
# Run all unit tests
pytest tests/unit -v

# Run with coverage
pytest --cov=scraper --cov-report=html

# Run specific test file
pytest tests/unit/test_cli.py -v
```

## 📋 Code Style

This project uses:
- **Ruff** for linting and formatting
- **Type hints** for all function signatures
- **Docstrings** for public functions and classes

Before committing:
```bash
# Check code style
ruff check src/ tests/

# Format code
ruff format src/ tests/
```

## 🔍 Pull Request Process

1. **Update documentation** if you're adding features
2. **Add tests** for new functionality
3. **Ensure all tests pass** locally
4. **Update CHANGELOG** (if applicable)
5. **Reference any related issues** in the PR description

### PR Checklist

- [ ] Tests added/updated and passing
- [ ] Code follows project style guidelines
- [ ] Documentation updated (if needed)
- [ ] Commit messages are clear and descriptive
- [ ] PR targets the correct branch (`main` or `apollo-integration`)

## 🚫 What NOT to Contribute

- **Apollo code to `main` branch** - Keep Apollo features separate
- **Breaking changes** without discussion - Open an issue first
- **Unrelated changes** - Keep PRs focused on a single feature/fix
- **Code without tests** - All new code needs test coverage

## 🐛 Reporting Bugs

1. **Check existing issues** to avoid duplicates
2. **Use the bug report template** (if available)
3. **Include**:
   - Python version
   - Operating system
   - Steps to reproduce
   - Expected vs actual behavior
   - Error messages/logs

## 💡 Suggesting Features

1. **Open an issue** with the `enhancement` label
2. **Describe the feature** and its use case
3. **Explain why** it would be valuable
4. **Consider** which branch it belongs in (`main` or `apollo-integration`)

## 📚 Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/scraping-emails-mod.git
cd scraping-emails-mod

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Run tests to verify setup
pytest tests/unit
```

## 🔐 Security

If you discover a security vulnerability:
1. **DO NOT** open a public issue
2. **Email** the maintainers directly
3. **Include** details about the vulnerability
4. **Wait** for a response before disclosing publicly

## 📄 License

By contributing, you agree that your contributions will be licensed under the same license as the project.

## ❓ Questions?

- Open an issue with the `question` label
- Check existing documentation in the `docs/` folder
- Review [BRANCHES.md](BRANCHES.md) for branch strategy details

## 🙏 Thank You!

Your contributions make this project better for everyone. We appreciate your time and effort!
