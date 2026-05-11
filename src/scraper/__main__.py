"""Entry point for python -m scraper."""
import sys

from scraper.cli import app

_COMMANDS = {
    "crawl-all",
    "scrape",
    "taxonomy",
    "ui",
    "acquisition-ui",
    "acquisition-import-csv",
    "acquisition-apollo-search",
    "--help",
    "-h",
    "--version",
    "--install-completion",
    "--show-completion",
}

if __name__ == "__main__":
    # Allow `python -m scraper TARGET [opts]` as shorthand for the scrape subcommand.
    if len(sys.argv) > 1 and sys.argv[1] not in _COMMANDS:
        sys.argv.insert(1, "scrape")
    app()
