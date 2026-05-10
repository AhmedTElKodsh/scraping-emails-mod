"""
User-agent rotation utilities.

Pool of realistic browser user-agent strings.
Matching research doc: Windows UA + Chrome, Firefox, Safari, Edge variants.
"""

import random

# Chrome user-agents (Windows, macOS, Linux)
CHROME_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
    ),
]

# Firefox user-agents
FIREFOX_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
]

# Safari user-agents
SAFARI_AGENTS = [
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/18.4 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
]

# Edge user-agents
EDGE_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"
    ),
]

# Mobile user-agents (iOS Safari, Android Chrome)
MOBILE_AGENTS = [
    (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_4 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 "
        "Mobile/15E148 Safari/604.1"
    ),
    (
        "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0.0.0 Mobile Safari/537.36"
    ),
    (
        "Mozilla/5.0 (iPad; CPU OS 18_4 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/18.4 Mobile/15E148 Safari/604.1"
    ),
]

ALL_AGENTS = CHROME_AGENTS + FIREFOX_AGENTS + SAFARI_AGENTS + EDGE_AGENTS + MOBILE_AGENTS


def get_random_agent(browser_type: str = "any") -> str:
    """
    Get a random user-agent string.
    browser_type: "chrome", "firefox", "safari", "edge", "mobile", or "any"
    """
    pools = {
        "chrome": CHROME_AGENTS,
        "firefox": FIREFOX_AGENTS,
        "safari": SAFARI_AGENTS,
        "edge": EDGE_AGENTS,
        "mobile": MOBILE_AGENTS,
        "any": ALL_AGENTS,
    }
    pool = pools.get(browser_type, ALL_AGENTS)
    return random.choice(pool)


def get_for_target(target: str) -> str:
    """
    Get recommended user-agent for target site.
    Research doc: yellowpages.com.eg -> Chrome (US-based desktop)
                          app.apollo.io -> Chrome (stealth automation)
    """
    if "yellowpages" in target:
        return CHROME_AGENTS[0]  # Chrome/136 Windows
    elif "apollo" in target:
        return CHROME_AGENTS[0]  # Chrome/136 Windows (consistent fingerprint)
    return get_random_agent("chrome")


def get_agent_with_browser(browser: str, platform: str = "windows") -> str:
    """
    Get a specific user-agent for a given browser and platform.
    Useful for matching TLS impersonation browser to user-agent string.
    """
    if browser == "chrome":
        if platform == "windows":
            return CHROME_AGENTS[0]
        elif platform == "mac":
            return CHROME_AGENTS[2]
        elif platform == "linux":
            return CHROME_AGENTS[3]
    elif browser == "firefox":
        if platform == "windows":
            return FIREFOX_AGENTS[0]
        elif platform == "mac":
            return FIREFOX_AGENTS[1]
        elif platform == "linux":
            return FIREFOX_AGENTS[2]
    return get_random_agent(browser)


if __name__ == "__main__":
    print(f"Random Chrome UA: {get_random_agent('chrome')}")
    print(f"For yellowpages: {get_for_target('yellowpages.com.eg')}")
    print(f"For apollo: {get_for_target('app.apollo.io')}")
    print(f"Any random: {get_random_agent('any')}")
