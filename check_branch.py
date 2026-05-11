#!/usr/bin/env python3
"""
Branch verification script for scraping-emails-mod repository.
Run this to check which branch you're on and what features are available.
"""

import subprocess
import sys
from pathlib import Path


def get_current_branch():
    """Get the current git branch name."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def check_apollo_files():
    """Check if Apollo files exist."""
    apollo_files = [
        Path("src/scraper/apollo_people_search.py"),
        Path("src/scraper/sites/apollo_public.py"),
    ]
    return all(f.exists() for f in apollo_files)


def main():
    """Main function to check branch status."""
    print("=" * 60)
    print("🌿 Branch Verification Tool")
    print("=" * 60)
    print()

    # Get current branch
    branch = get_current_branch()
    if not branch:
        print("❌ Error: Not a git repository or git not installed")
        sys.exit(1)

    print(f"📍 Current Branch: {branch}")
    print()

    # Check Apollo files
    has_apollo = check_apollo_files()

    if branch == "main":
        print("✅ You are on the MAIN branch")
        print()
        print("Features Available:")
        print("  ✅ YellowPages Egypt scraper")
        print("  ✅ CSV import/export")
        print("  ✅ Acquisition database")
        print("  ✅ Streamlit UI")
        print("  ✅ Browser automation")
        print("  ❌ Apollo API integration (NOT available)")
        print()
        
        if has_apollo:
            print("⚠️  WARNING: Apollo files detected on main branch!")
            print("   This should not happen. The branch may be corrupted.")
        else:
            print("✅ Branch integrity: OK (no Apollo files)")
        
        print()
        print("To access Apollo features:")
        print("  git checkout apollo-integration")

    elif branch == "apollo-integration":
        print("✅ You are on the APOLLO-INTEGRATION branch")
        print()
        print("Features Available:")
        print("  ✅ YellowPages Egypt scraper")
        print("  ✅ CSV import/export")
        print("  ✅ Acquisition database")
        print("  ✅ Streamlit UI")
        print("  ✅ Browser automation")
        print("  ✅ Apollo API integration (AVAILABLE)")
        print()
        
        if has_apollo:
            print("✅ Branch integrity: OK (Apollo files present)")
        else:
            print("⚠️  WARNING: Apollo files NOT found!")
            print("   This branch should contain Apollo integration.")
        
        print()
        print("To use core features only:")
        print("  git checkout main")

    else:
        print(f"ℹ️  You are on a custom branch: {branch}")
        print()
        if has_apollo:
            print("Apollo files: ✅ Present")
        else:
            print("Apollo files: ❌ Not present")
        print()
        print("Standard branches:")
        print("  • main - Core features only")
        print("  • apollo-integration - Full features with Apollo")

    print()
    print("=" * 60)
    print("For more information, see:")
    print("  • README.md")
    print("  • BRANCHES.md")
    print("  • docs/BRANCH_COMPARISON.md")
    print("=" * 60)


if __name__ == "__main__":
    main()
