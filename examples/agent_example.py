"""How an AI agent (or any script) uses a profile a human already logged in to.

    pip install playwright   (no need to download Playwright's browsers: we use your real Chrome)
"""
from playwright.sync_api import sync_playwright
from chrome_profile_hub import open_chrome, agent_page, pick

prof = pick("notion")                       # a profile that already has a Notion login
if not prof:
    raise SystemExit("No profile is logged in to Notion - ask a human to log in from the hub first.")

with sync_playwright() as p:
    browser, ctx = open_chrome(p, prof["key"], task="read Notion inbox")   # row turns yellow in the hub
    page = agent_page(ctx, "https://www.notion.so")                        # our own tab, closed on exit
    print(page.title())
    # never call browser.close(): it would close the human's window too
